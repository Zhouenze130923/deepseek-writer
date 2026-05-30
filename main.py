#!/usr/bin/env python3
"""DeepSeek Writer — AI 写作终端助手。"""

from __future__ import annotations
import asyncio
import re
import sys
import threading

from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown

from config import Config
from orchestrator import Orchestrator
from project import Project, Volume, Chapter
from utils.file_manager import FileManager
from utils.exporter import Exporter
from utils.memory import MemoryStore
from utils.display import (
    console, print_banner, print_help, print_styles,
    print_project_status, print_outline, print_characters,
    print_success, print_error, print_info, print_warning,
    print_streaming,
)
from templates import list_templates, get_template, template_to_prompt


class DeepSeekWriter:
    def __init__(self):
        self.config = Config.load()
        self.file_manager = FileManager()
        self.orchestrator: Orchestrator | None = None
        self.project: Project | None = None
        self.brief: dict | None = None
        self.memory: MemoryStore | None = None
        self._lock = threading.Lock()
        self.fast_mode = False
        self.review_rounds = 1
        self.parallel_editors = False  # Toggle triple-editor mode

    def run(self):
        print_banner()
        self._init_orchestrator()
        print_info(f"模型: {self.config.provider.upper()} — {self.config.active_model}")
        print_info("输入灵感开始 | /help 命令 | /fast 极速 | /triple 三编辑并行")

        while True:
            try:
                user_input = Prompt.ask("\n[bold green]请输入小说灵感[/bold green]").strip()
                if not user_input:
                    continue
                if user_input.startswith("/"):
                    self._handle_command(user_input)
                else:
                    self._auto_write(user_input)
            except KeyboardInterrupt:
                console.print("\n")
                if Confirm.ask("是否退出?"):
                    break
            except EOFError:
                break
        self._shutdown()

    def _init_orchestrator(self):
        if not self.config.api_key:
            print_warning("未配置 API 密钥，输入 /config 配置")
        self.orchestrator = Orchestrator(self.config)

    def _check_api(self) -> bool:
        if not self.config.api_key:
            print_error("请先输入 /config")
            return False
        return True

    # ===== Commands =====

    def _handle_command(self, cmd: str):
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        handlers = {
            "/help": self._cmd_help, "/config": self._cmd_config,
            "/templates": self._cmd_templates, "/list": self._cmd_list,
            "/load": self._cmd_load, "/status": self._cmd_status,
            "/stats": self._cmd_stats, "/style": self._cmd_style,
            "/quit": self._cmd_quit,
            "/fast": self._cmd_fast, "/strict": self._cmd_strict,
            "/triple": self._cmd_triple,
            "/import": self._cmd_import,
            "/export": self._cmd_export,
            "/continue": self._cmd_continue,
            "/retry": self._cmd_retry,
            "/backtrack": self._cmd_backtrack,
            "/memory": self._cmd_memory,
        }
        handler = handlers.get(command)
        if handler:
            handler(args)
        else:
            print_warning(f"未知命令: {command}")

    def _cmd_help(self, _):
        console.print("""
[bold cyan]DeepSeek Writer[/bold cyan]

[bold]写作[/bold] — 输入灵感自动全流程
[bold]管理[/bold]
  [cyan]/continue[/cyan]    继续未完成章节
  [cyan]/retry[/cyan] N     重写第N章
  [cyan]/backtrack[/cyan] N 回到第N章，删后续重写
  [cyan]/import[/cyan] 文件 导入人设/世界观.md
  [cyan]/export[/cyan]      多格式导出
[bold]模式[/bold]
  [cyan]/fast[/cyan]      极速（跳过审阅）
  [cyan]/strict[/cyan]    严格（2轮审阅）
  [cyan]/triple[/cyan]    三编辑并审（逻辑+风格+伏笔）
[bold]查看[/bold]
  [cyan]/status[/cyan]  [cyan]/stats[/cyan]  [cyan]/memory[/cyan]
  [cyan]/templates[/cyan] [cyan]/list[/cyan] [cyan]/load[/cyan]
  [cyan]/config[/cyan]  [cyan]/quit[/cyan]
""")

    def _cmd_fast(self, _):
        self.fast_mode = not self.fast_mode
        self.review_rounds = 0 if self.fast_mode else 1
        print_success(f"极速={'ON' if self.fast_mode else 'OFF'}")

    def _cmd_strict(self, _):
        self.review_rounds = 2; self.fast_mode = False
        print_success("严格模式: 2轮审阅")

    def _cmd_triple(self, _):
        self.parallel_editors = not self.parallel_editors
        print_success(f"三编辑并审={'ON' if self.parallel_editors else 'OFF'}")

    def _cmd_import(self, args):
        if not args:
            print_warning("用法: /import 文件路径.md")
            return
        path = args.strip()
        try:
            content = open(path).read()
            self._imported_constraints = content[:3000]
            total = len(content)
            print_success(f"已导入 {path} ({total} 字)")
            console.print(f"[dim]前3000字将作为约束注入人物设计...[/dim]")
        except FileNotFoundError:
            print_error(f"文件不存在: {path}")

    def _cmd_export(self, _):
        if not self.project:
            print_warning("暂无项目")
            return
        exp = Exporter(self.project)
        console.print("[bold cyan]导出格式[/bold cyan]")
        results = {}
        results["md"] = exp.export_markdown()
        results["txt"] = exp.export_txt()
        console.print(f"[green]MD: {results['md']}[/green]")
        console.print(f"[green]TXT: {results['txt']}[/green]")
        for fmt in ["epub", "pdf", "docx"]:
            r = getattr(exp, f"export_{fmt}")()
            console.print(f"[dim]{fmt.upper()}: {r}[/dim]")
        print_success("导出完成")

    def _cmd_continue(self, _):
        if not self.project:
            print_warning("暂无项目，/load 加载")
            return
        undone = self.project.get_next_pending_chapter()
        if not undone:
            print_success("所有章节已完成！")
            return
        vi, ci, chapter = undone
        volume = self.project.volumes[vi]
        console.print(f"继续: 第{volume.volume_number}卷第{chapter.chapter_number}章「{chapter.chapter_title}」")
        self._write_all_volumes()

    def _cmd_retry(self, args):
        if not self.project:
            print_warning("暂无项目")
            return
        try:
            ch_num = int(args) if args else 0
        except ValueError:
            print_warning("用法: /retry 章节号")
            return
        for vi, volume in enumerate(self.project.volumes):
            for ci, chapter in enumerate(volume.chapters):
                if chapter.chapter_number == ch_num:
                    chapter.status = "pending"
                    chapter.content = ""
                    print_success(f"第{ch_num}章已重置，下次写作时重新生成")
                    return
        print_error(f"未找到第{ch_num}章")

    def _cmd_backtrack(self, args):
        if not self.project:
            print_warning("暂无项目")
            return
        try:
            ch_num = int(args) if args else 0
        except ValueError:
            print_warning("用法: /backtrack 章节号")
            return
        if not Confirm.ask(f"将删除第{ch_num}章及之后所有内容，确认?", default=False):
            return
        found = False
        for vi, volume in enumerate(self.project.volumes):
            for ci, chapter in enumerate(volume.chapters):
                if chapter.chapter_number >= ch_num:
                    chapter.status = "pending"
                    chapter.content = ""
                    found = True
        if found:
            print_success(f"已回溯至第{ch_num}章之前")
        else:
            print_error(f"未找到第{ch_num}章")

    def _cmd_memory(self, _):
        if self.memory:
            s = self.memory.stats()
            console.print(f"记忆系统: {s['backend']} | {s['count']} 条")
        else:
            print_info("无记忆数据")

    def _cmd_templates(self, _):
        from templates import TEMPLATES
        console.print("\n[bold cyan]写作模版[/bold cyan]\n")
        for name, t in TEMPLATES.items():
            console.print(f"[bold]{name}[/bold] ({t.get('scale','')}) — {t.get('description','')}")

    def _cmd_config(self, _):
        console.print("\n[bold cyan]配置 API[/bold cyan]\n")
        provider = Prompt.ask("提供商", choices=["deepseek", "claude"], default=self.config.provider)
        self.config.provider = provider
        if provider == "deepseek":
            self.config.deepseek_api_key = Prompt.ask("DeepSeek API Key", default=self.config.deepseek_api_key)
            from llm.models import DEEPSEEK_MODELS
            models = list(DEEPSEEK_MODELS.keys())
            self.config.model = Prompt.ask("模型", choices=models, default=self.config.model)
        else:
            self.config.claude_api_key = Prompt.ask("Claude API Key", default=self.config.claude_api_key)
            from llm.models import CLAUDE_MODELS
            models = list(CLAUDE_MODELS.keys())
            self.config.claude_model = Prompt.ask("模型", choices=models, default=self.config.claude_model)
        self.config.save()
        self._init_orchestrator()
        print_success("已保存")

    def _cmd_list(self, _):
        projects = self.file_manager.list_projects()
        console.print("\n[bold cyan]已保存[/bold cyan]\n")
        for i, n in enumerate(projects or [], 1):
            console.print(f"  {i}. {n}")
        if not projects:
            print_info("无")

    def _cmd_load(self, args):
        if not args:
            self._cmd_list("")
            args = Prompt.ask("项目名称")
        proj = self.file_manager.load(args)
        if proj:
            self.project = proj; self.brief = None
            self.memory = MemoryStore(proj.title)
            print_success(f"已加载「{proj.title}」")
            self._cmd_status("")
            undone = self.project.get_next_pending_chapter()
            if undone:
                print_info("有未完成章节，输入任意内容或 /continue 继续")
        else:
            print_error(f"未找到: {args}")

    def _cmd_status(self, _):
        if not self.project:
            print_warning("暂无项目，输入灵感开始")
            return
        total_words = sum(len(c.content) for v in self.project.volumes for c in v.chapters)
        total_ch = sum(len(v.chapters) for v in self.project.volumes)
        done_ch = sum(1 for v in self.project.volumes for c in v.chapters if c.status == "done")
        console.print(f"\n[bold]《{self.project.title}》[/bold] {self.project.genre} | {self.project.template or '自动'}")
        console.print(f"{len(self.project.volumes)}卷 {done_ch}/{total_ch}章 | 约{total_words}字")
        if self.project.volumes:
            print_project_status(self.project)

    def _cmd_stats(self, _):
        if not self.project:
            print_warning("暂无项目")
            return
        fs = self.project.foreshadowing.stats()
        bs = self.project.bible.stats()
        total_words = sum(len(c.content) for v in self.project.volumes for c in v.chapters)
        total_ch = sum(len(v.chapters) for v in self.project.volumes)
        done_ch = sum(1 for v in self.project.volumes for c in v.chapters if c.status == "done")
        console.print(f"\n[bold cyan]《{self.project.title}》统计[/bold cyan]")
        console.print(f"进度: {done_ch}/{total_ch}章 | 约{total_words}字")
        console.print(f"伏笔: {fs['total']}总 {fs['resolved']}已收 ({fs['rate']})")
        if fs['critical_unresolved'] > 0:
            print_warning(f"  {fs['critical_unresolved']}个关键伏笔未收！")
        console.print(f"圣经: {bs['total']}条")
        if self.memory:
            ms = self.memory.stats()
            console.print(f"记忆: {ms['backend']} {ms['count']}条")

    def _cmd_style(self, _):
        print_styles()

    def _cmd_quit(self, _):
        if self.project:
            self._save_project()
        console.print("[cyan]再见！[/cyan]")
        sys.exit(0)

    # ===== Auto pipeline =====

    def _auto_write(self, user_idea: str):
        if not self._check_api():
            return

        if self.project and self.project.volumes:
            undone = self.project.get_next_pending_chapter()
            if undone:
                if Confirm.ask(f"「{self.project.title}」有未完成章节，继续? (n=新建)", default=True):
                    if not self.brief and self.project.characters:
                        self._run_stage_condense()
                    self._write_all_volumes()
                    return

        template = self._pick_template()
        constraints = getattr(self, '_imported_constraints', '')
        self.project = Project(premise=user_idea, template=template["name"] if template else "")
        self.memory = MemoryStore("")

        # Stage 1 + user review
        self._run_stage_outline(user_idea, template)
        if not self.fast_mode and not Confirm.ask("大纲是否满意? (y=继续, n=重新生成)", default=True):
            self._run_stage_outline(user_idea, template)

        # Stage 2 + user review
        self._run_stage_characters(constraints)
        if not self.fast_mode and not Confirm.ask("人物设定是否满意? (y=继续, n=重新生成)", default=True):
            self._run_stage_characters(constraints)

        self._run_stage_condense()

        if self.memory:
            self.memory.project_name = self.project.title
            for c in self.project.characters.get("characters", []):
                self.memory.add_character_fact(c.get("name", ""), c.get("personality", ""))
            for rule in self.project.characters.get("world_building", {}).get("rules", []):
                self.memory.add_world_rule(rule)

        self._write_all_volumes()
        self._finalize()
        # Clean up import after use
        if hasattr(self, '_imported_constraints'):
            delattr(self, '_imported_constraints')

    def _pick_template(self) -> dict | None:
        templates = list_templates()
        console.print("\n[bold cyan]选择写作模版（回车=自动）[/bold cyan]")
        for i, name in enumerate(templates, 1):
            console.print(f"  {i}. {name}")
        choice = Prompt.ask("模版编号", default="0")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(templates):
                from templates import TEMPLATES
                name = templates[idx]
                console.print(f"[green]已选: {name}[/green]")
                return {"name": name, **TEMPLATES[name]}
        except (ValueError, IndexError):
            pass
        return None

    def _run_stage_outline(self, user_idea: str, template: dict | None):
        console.print("\n[bold yellow]━━━ 1. 生成大纲 ━━━[/bold yellow]")
        if template:
            console.print(f"[dim]模版: {template['name']} | {template.get('scale','')}[/dim]")
        try:
            template_guide = template_to_prompt(template) if template else ""
            outline = self.orchestrator.generate_outline(premise=user_idea, template_guide=template_guide)
            self.project.title = outline.get("title", "未命名")
            self.project.genre = outline.get("genre", "")
            self.project.theme = outline.get("theme", "")
            self.project.tone = outline.get("tone", "")
            self.project.volumes = []
            for v in outline.get("volumes", []):
                volume = Volume(volume_number=v["volume_number"], volume_title=v["volume_title"], synopsis=v["synopsis"])
                for c in v.get("chapters", []):
                    volume.chapters.append(Chapter(
                        chapter_number=c["chapter_number"], chapter_title=c["chapter_title"],
                        synopsis=c["synopsis"], key_events=c.get("key_events", []),
                        pov_character=c.get("pov_character", ""),
                        word_count_target=min(c.get("word_count_target", 3000), 3000),
                    ))
                self.project.volumes.append(volume)
            self.project.current_stage = "outlined"
            self._save_project()
            print_outline(outline)
        except Exception as e:
            print_error(f"大纲失败: {e}")
            raise

    def _run_stage_characters(self, constraints: str = ""):
        console.print("\n[bold yellow]━━━ 2. 设计人物与风格 ━━━[/bold yellow]")
        try:
            character_design = self.orchestrator.design_characters(
                outline=self.project.to_dict(), style="自动匹配", constraints=constraints,
            )
            self.project.characters = character_design
            self.project.plot_arcs = character_design.get("plot_arcs", {})
            self.project.world_building = character_design.get("world_building", {})
            self.project.writing_style = character_design.get("writing_style", {})
            self.project.style_reference = character_design.get("style_reference", {})
            self.project.current_stage = "characters_done"
            for c in character_design.get("characters", []):
                self.project.bible.establish("character", f"{c['name']}.role", c.get("role", ""), 0, 0)
                self.project.bible.establish("character", f"{c['name']}.personality", c.get("personality", ""), 0, 0)
            for rule in character_design.get("world_building", {}).get("rules", []):
                self.project.bible.establish("world", f"rule.{rule[:30]}", rule, 0, 0)
            self._save_project()
            print_characters(character_design)
        except Exception as e:
            print_error(f"人物设计失败: {e}")
            raise

    def _run_stage_condense(self):
        console.print("\n[bold yellow]━━━ 2.5 凝练写作指南 ━━━[/bold yellow]")
        console.print("[dim]程序化提取，零token消耗...[/dim]")
        try:
            self.brief = self.orchestrator.condense(
                outline=self.project.to_dict(),
                characters=self.project.characters,
                writing_style=self.project.writing_style,
            )
            chars = len(self.brief.get("characters_brief", []))
            console.print(f"[dim]角色:{chars} 卷:{len(self.brief.get('volume_plan',[]))}[/dim]")
            print_success("凝练完成")
        except Exception as e:
            print_error(f"凝练失败: {e}")
            raise

    def _write_all_volumes(self):
        total_chapters = sum(len(v.chapters) for v in self.project.volumes)
        total_volumes = len(self.project.volumes)
        editor_mode = "三编辑并行" if self.parallel_editors else (f"{self.review_rounds}轮审阅" if not self.fast_mode else "无审阅")
        console.print(f"\n[bold yellow]━━━ 3+. 写作 ({editor_mode}) ━━━[/bold yellow]")
        console.print(f"[bold]《{self.project.title}》[/bold] {total_volumes}卷 {total_chapters}章\n")
        self.project.current_stage = "writing"

        if total_volumes > 1 and self.brief:
            asyncio.run(self._write_volumes_parallel())
        else:
            for vi, volume in enumerate(self.project.volumes):
                self._write_volume_sequential(vi, volume)
        self.project.current_stage = "done"

    def _write_volume_sequential(self, vi, volume):
        console.print(f"\n[bold cyan]━━━ 第{volume.volume_number}卷「{volume.volume_title}」━━━[/bold cyan]")
        vol_plan = self.brief.get("volume_plan", []) if self.brief else []
        vol_brief = vol_plan[vi] if vi < len(vol_plan) else {}
        volume_goal = vol_brief.get("goal", volume.synopsis)
        for ci, chapter in enumerate(volume.chapters):
            if chapter.status == "done":
                continue
            ch_brief = vol_brief.get("chapters", [])
            ch_plan = ch_brief[ci] if ci < len(ch_brief) else {}
            self._write_and_review_one(vi, ci, chapter, volume_goal,
                                       ch_plan.get("must_happen", chapter.synopsis),
                                       ch_plan.get("pov", chapter.pov_character),
                                       self._get_prev_context(vi, ci))
            self._save_project()
        volume.status = "done"

    async def _write_volumes_parallel(self):
        pending = [vi for vi, v in enumerate(self.project.volumes)
                   if any(c.status == "pending" for c in v.chapters)]
        n = min(len(pending), 5)
        console.print(f"[dim]{n} 个子代理各负责一卷...[/dim]\n")

        async def write_one_volume(vi):
            volume = self.project.volumes[vi]
            vol_plan = self.brief.get("volume_plan", [])
            vol_brief = vol_plan[vi] if vi < len(vol_plan) else {}
            volume_goal = vol_brief.get("goal", volume.synopsis)
            console.print(f"[cyan]📖 第{volume.volume_number}卷开始[/cyan]")
            for ci, chapter in enumerate(volume.chapters):
                if chapter.status == "done":
                    continue
                ch_brief = vol_brief.get("chapters", [])
                ch_plan = ch_brief[ci] if ci < len(ch_brief) else {}
                await asyncio.to_thread(
                    self._write_and_review_one, vi, ci, chapter, volume_goal,
                    ch_plan.get("must_happen", chapter.synopsis),
                    ch_plan.get("pov", chapter.pov_character),
                    self._get_prev_context(vi, ci),
                )
                self._save_project()
            volume.status = "done"
            console.print(f"[green]✅ 第{volume.volume_number}卷完成[/green]")

        batch_size = min(5, len(pending))
        for i in range(0, len(pending), batch_size):
            await asyncio.gather(*(write_one_volume(vi) for vi in pending[i:i+batch_size]))

    def _write_and_review_one(self, vi, ci, chapter, volume_goal, must_happen, pov, prev):
        volume = self.project.volumes[vi]
        target = chapter.word_count_target
        console.print(f"\n[bold cyan]第{chapter.chapter_number}章「{chapter.chapter_title}」 目标{target}字[/bold cyan]")
        console.print(f"[dim]{must_happen}[/dim]\n")

        try:
            writer = self.orchestrator._get_writer()
            _, resolve_fs = self.orchestrator.get_foreshadowing_context(
                self.project, volume.volume_number, chapter.chapter_number)
            bible_ctx = self.orchestrator.get_bible_context(
                self.project, volume.volume_number, chapter.chapter_number)

            # Memory retrieval
            mem_ctx = ""
            if self.memory:
                mem_ctx = self.memory.get_context_for_chapter(
                    volume.volume_number, chapter.chapter_number, must_happen)

            content = ""
            for chunk in writer.write_chapter_stream(
                brief=self.brief or {},
                volume_number=volume.volume_number, volume_title=volume.volume_title,
                volume_goal=volume_goal, chapter_number=chapter.chapter_number,
                chapter_title=chapter.chapter_title, must_happen=must_happen, pov=pov,
                previous_context=prev,
                plant_foreshadowing="根据大纲自然植入伏笔",
                resolve_foreshadowing=resolve_fs,
                bible_context=bible_ctx + "\n" + mem_ctx,
            ):
                content += chunk
                print_streaming(chunk)
            word_count = len(content)
            console.print(f"\n[dim]初稿: {word_count}/{target} 字[/dim]")

            # Auto-expand
            expand_count = 0
            while word_count < target * 0.7 and expand_count < 3:
                expand_count += 1
                shortage = target - word_count
                console.print(f"[yellow]⚠ 扩展第{expand_count}次 (缺{shortage}字)...[/yellow]\n")
                expansion = ""
                for chunk in writer.write_chapter_stream(
                    brief=self.brief or {},
                    volume_number=volume.volume_number, volume_title=volume.volume_title,
                    volume_goal=volume_goal, chapter_number=chapter.chapter_number,
                    chapter_title=chapter.chapter_title,
                    must_happen=f"扩展本章到{target}字。保留已有内容，增加细节描写、对话、场景。需增加约{shortage}字。",
                    pov=pov, previous_context=content[-500:],
                    plant_foreshadowing="", resolve_foreshadowing="", bible_context="",
                ):
                    expansion += chunk
                    print_streaming(chunk)
                content += "\n" + expansion
                word_count = len(content)

            chapter.content = content
            console.print(f"\n[green]✅ 完成 ({word_count} 字)[/green]")

            with self._lock:
                self.project.bible.establish("plot", f"V{volume.volume_number}C{chapter.chapter_number}.synopsis",
                                             chapter.synopsis, volume.volume_number, chapter.chapter_number)

            # Store in memory
            if self.memory:
                self.memory.add_chapter_summary(
                    volume.volume_number, chapter.chapter_number,
                    chapter.synopsis, pov, ", ".join(chapter.key_events[:3]))

        except Exception as e:
            print_error(f"写作失败: {e}")
            chapter.status = "pending"
            return

        if not self.fast_mode:
            chapter.status = "reviewing"
            self._review_revise_loop(vi, ci, chapter)
        chapter.status = "done"

    def _review_revise_loop(self, vi, ci, chapter):
        if self.review_rounds <= 0:
            return

        # Use parallel editors if enabled
        parallel = self.parallel_editors

        for round_num in range(1, self.review_rounds + 1):
            console.print()
            mode = "三编辑并行" if parallel else "综合"
            console.print(f"[bold red]🔍 编辑审阅 (第{round_num}轮, {mode})[/bold red]")

            report = ""
            try:
                report = self.orchestrator.review_chapter(
                    self.project, vi, ci, self.brief or {},
                    parallel=parallel, on_chunk=None if parallel else print_streaming,
                )
                if parallel:
                    console.print(report)
                else:
                    console.print("")
            except Exception as e:
                print_warning(f"审阅跳过: {e}")
                return

            if not self._report_has_issues(report):
                console.print("[dim]编辑: 无重大问题，跳过修改[/dim]")
                return

            console.print(f"[bold yellow]✏️ 修改 (第{round_num}轮)[/bold yellow]\n")
            try:
                writer = self.orchestrator._get_writer()
                revised = ""
                for chunk in writer.revise_chapter_stream(
                    brief=self.brief or {}, original_content=chapter.content, editor_report=report,
                ):
                    revised += chunk
                    print_streaming(chunk)
                chapter.content = revised
                console.print(f"\n[green]✅ 修改完成 ({len(revised)} 字)[/green]")
            except Exception as e:
                print_warning(f"修改跳过: {e}")
                return

    def _report_has_issues(self, report: str) -> bool:
        """判断编辑报告是否包含需要修改的实际问题。无问题则跳过修改以节省时间/token。"""
        if not report.strip():
            return False
        # Explicit issue markers → must revise
        if re.search(r'⚠|不合格|必须修改|严重问题|有矛盾|不合理|硬伤', report):
            return True
        # All sections passed → skip
        pass_count = len(re.findall(r'通过|逻辑通过|文笔通过|伏笔通过|无问题|没问题|合格|没有发现问题|未发现问题', report))
        if pass_count >= 3:
            return False
        # If any section explicitly says "通过", and no issues found, skip
        if re.search(r'通过', report) and not re.search(r'需修改|建议(删除|重写|修改|调整)', report):
            return False
        # Default: if in doubt, skip (don't waste time on minor suggestions)
        return False

    def _get_prev_context(self, vi, ci):
        if ci == 0:
            return ""
        prev = self.project.volumes[vi].chapters[ci - 1]
        if prev.content:
            return f"上一章结尾: ...{prev.content[-300:]}"
        return f"前一章「{prev.chapter_title}」: {prev.synopsis}"

    def _finalize(self):
        console.print("\n[bold green]━━━ 小说创作完成！━━━[/bold green]")
        self.project.current_stage = "done"
        proj_dir = self.file_manager.save(self.project)

        total_words = sum(len(c.content) for v in self.project.volumes for c in v.chapters)
        total_chapters = sum(len(v.chapters) for v in self.project.volumes)
        total_target = sum(c.word_count_target for v in self.project.volumes for c in v.chapters)
        fs = self.project.foreshadowing.stats()
        mode_info = []
        if self.fast_mode: mode_info.append("极速")
        if self.parallel_editors: mode_info.append("三编辑并行")
        mode_str = ", ".join(mode_info) if mode_info else "标准"

        console.print(f"\n[bold]《{self.project.title}》[/bold] ({mode_str})")
        console.print(f"模版: {self.project.template or '自动'} | {len(self.project.volumes)}卷 {total_chapters}章")
        console.print(f"字数: 约{total_words}字 (目标{total_target}) | 达标: {min(100,int(total_words/max(1,total_target)*100))}%")
        console.print(f"伏笔回收: {fs['rate']} | 圣经: {self.project.bible.stats()['total']}条")
        if self.memory:
            ms = self.memory.stats()
            console.print(f"记忆: {ms['backend']} {ms['count']}条")

        console.print(f"\n[cyan]已保存: {proj_dir}[/cyan]")
        console.print(f"[dim]输入 /export 多格式导出[/dim]")

    def _save_project(self):
        if self.project:
            with self._lock:
                self.file_manager.save(self.project)

    def _shutdown(self):
        if self.project:
            self._save_project()
        console.print("[cyan]再见！[/cyan]")


def main():
    app = DeepSeekWriter()
    app.run()


if __name__ == "__main__":
    main()
