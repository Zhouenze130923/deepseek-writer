#!/usr/bin/env python3
"""DeepSeek Writer — AI 写作终端助手。

输入灵感 → 自动完成整篇小说。
内置 6 种写作模版、伏笔追踪、世界圣经防吃书系统。
"""

from __future__ import annotations
import asyncio
import re
import sys
import threading

from rich.prompt import Prompt, Confirm

from config import Config
from orchestrator import Orchestrator
from project import Project, Volume, Chapter
from utils.file_manager import FileManager
from utils.display import (
    console, print_banner, print_help, print_styles,
    print_project_status, print_outline, print_characters,
    print_success, print_error, print_info, print_warning,
    print_streaming,
)
from templates import list_templates, get_template, template_to_prompt


class DeepSeekWriter:
    """输入灵感 → 自动成书。"""

    def __init__(self):
        self.config = Config.load()
        self.file_manager = FileManager()
        self.orchestrator: Orchestrator | None = None
        self.project: Project | None = None
        self.brief: dict | None = None
        self._lock = threading.Lock()
        self.fast_mode = False
        self.review_rounds = 1  # 1 round by default

    def run(self):
        print_banner()
        self._init_orchestrator()
        print_info(f"模型: {self.config.provider.upper()} — {self.config.active_model}")
        print_info("直接输入小说创意，自动完成全流程")
        print_info("/help 命令 | /fast 极速 | /strict 严格 | /templates 模版")

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
            print_warning("尚未配置 API 密钥，输入 /config 配置")
        self.orchestrator = Orchestrator(self.config)

    def _check_api(self) -> bool:
        if not self.config.api_key:
            print_error("请先输入 /config 配置 API 密钥")
            return False
        return True

    # ===== Commands =====

    def _handle_command(self, cmd: str):
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handlers = {
            "/help": self._cmd_help, "/config": self._cmd_config,
            "/templates": self._cmd_templates,
            "/list": self._cmd_list, "/load": self._cmd_load,
            "/status": self._cmd_status, "/style": self._cmd_style,
            "/stats": self._cmd_stats, "/quit": self._cmd_quit,
            "/fast": self._cmd_fast, "/strict": self._cmd_strict,
        }
        handler = handlers.get(command)
        if handler:
            handler(args)
        else:
            print_warning(f"未知命令: {command}")

    def _cmd_help(self, _):
        console.print("""
[bold cyan]DeepSeek Writer[/bold cyan]

[bold]直接写小说[/bold] — 输入灵感，自动全流程

[bold]模式[/bold]
  [cyan]/fast[/cyan]     极速模式（跳过审阅，省50%时间+token）
  [cyan]/strict[/cyan]   严格模式（2轮审阅修改）

[bold]命令[/bold]
  [cyan]/templates[/cyan] 写作模版
  [cyan]/config[/cyan]    API和模型
  [cyan]/status[/cyan]    进度
  [cyan]/stats[/cyan]     伏笔/圣经统计
  [cyan]/list[/cyan]      已保存
  [cyan]/load[/cyan]      加载
  [cyan]/quit[/cyan]      退出
""")

    def _cmd_fast(self, _):
        self.fast_mode = not self.fast_mode
        self.review_rounds = 0 if self.fast_mode else 1
        print_success(f"极速={'ON' if self.fast_mode else 'OFF'}（跳过编辑审阅）")

    def _cmd_strict(self, _):
        self.review_rounds = 2
        self.fast_mode = False
        print_success("严格模式：2轮审阅×2轮修改")

    def _cmd_templates(self, _):
        from templates import TEMPLATES
        console.print("\n[bold cyan]写作模版[/bold cyan]\n")
        for name, t in TEMPLATES.items():
            console.print(f"[bold]{name}[/bold] ({t.get('scale','')}) — {t.get('description','')}")
            console.print(f"  适合: {'、'.join(t.get('best_for',[]))}\n")

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
        print_success("配置已保存")

    def _cmd_list(self, _):
        projects = self.file_manager.list_projects()
        if not projects:
            print_info("暂无项目")
            return
        console.print("\n[bold cyan]已保存[/bold cyan]\n")
        for i, name in enumerate(projects, 1):
            console.print(f"  {i}. {name}")

    def _cmd_load(self, args):
        if not args:
            self._cmd_list("")
            args = Prompt.ask("项目名称")
        project = self.file_manager.load(args)
        if project:
            self.project = project
            self.brief = None
            print_success(f"已加载「{project.title}」")
            self._cmd_status("")
            undone = self.project.get_next_pending_chapter()
            if undone:
                print_info("有未完成章节，输入任意内容继续")
            else:
                print_success("已完成！")
        else:
            print_error(f"未找到: {args}")

    def _cmd_status(self, _):
        if not self.project:
            print_warning("暂无项目，输入灵感开始")
            return
        console.print(f"\n[bold]《{self.project.title}》[/bold]")
        console.print(f"类型: {self.project.genre} | 模版: {self.project.template or '自动'} | 阶段: {self.project.current_stage}")
        if self.project.volumes:
            print_project_status(self.project)

    def _cmd_stats(self, _):
        if not self.project:
            print_warning("暂无项目")
            return
        fs = self.project.foreshadowing.stats()
        bs = self.project.bible.stats()
        console.print(f"\n[bold cyan]《{self.project.title}》统计[/bold cyan]")
        console.print(f"\n[bold]伏笔[/bold] {fs['total']}总 {fs['resolved']}回收 {fs['unresolved']}待回收 ({fs['rate']})")
        if fs['critical_unresolved'] > 0:
            print_warning(f"  {fs['critical_unresolved']} 个关键伏笔未回收！")
        console.print(f"\n[bold]圣经[/bold] {bs['total']} 条")
        for cat, count in bs.items():
            if cat != "total":
                console.print(f"  {cat}: {count}")
        total_words = sum(len(c.content) for v in self.project.volumes for c in v.chapters)
        total_chapters = sum(len(v.chapters) for v in self.project.volumes)
        console.print(f"\n[bold]篇幅[/bold] {len(self.project.volumes)}卷 {total_chapters}章 约{total_words}字")

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

        # Pick template
        template = self._pick_template()
        self.project = Project(premise=user_idea, template=template["name"] if template else "")

        self._run_stage_outline(user_idea, template)
        self._run_stage_characters()
        self._run_stage_condense()
        self._write_all_volumes()
        self._finalize()

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
        console.print()
        console.print("[bold yellow]━━━ 1. 生成大纲 ━━━[/bold yellow]")
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
                volume = Volume(
                    volume_number=v["volume_number"],
                    volume_title=v["volume_title"],
                    synopsis=v["synopsis"],
                )
                for c in v.get("chapters", []):
                    # Cap per-chapter target at a realistic LLM output
                    raw_target = c.get("word_count_target", 3000)
                    chapter = Chapter(
                        chapter_number=c["chapter_number"],
                        chapter_title=c["chapter_title"],
                        synopsis=c["synopsis"],
                        key_events=c.get("key_events", []),
                        pov_character=c.get("pov_character", ""),
                        word_count_target=min(raw_target, 3000),  # per-pass cap
                    )
                    volume.chapters.append(chapter)
                self.project.volumes.append(volume)

            self.project.current_stage = "outlined"
            self._save_project()
            print_outline(outline)
        except Exception as e:
            print_error(f"大纲失败: {e}")
            raise

    def _run_stage_characters(self):
        console.print()
        console.print("[bold yellow]━━━ 2. 设计人物与风格 ━━━[/bold yellow]")

        try:
            character_design = self.orchestrator.design_characters(
                outline=self.project.to_dict(), style="自动匹配",
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
        console.print()
        console.print("[bold yellow]━━━ 2.5 凝练写作指南 ━━━[/bold yellow]")
        console.print("[dim]程序化提取，零token消耗...[/dim]")

        try:
            self.brief = self.orchestrator.condense(
                outline=self.project.to_dict(),
                characters=self.project.characters,
                writing_style=self.project.writing_style,
            )
            chars = len(self.brief.get("characters_brief", []))
            rules = len(self.brief.get("style_rules", []))
            vols = len(self.brief.get("volume_plan", []))
            console.print(f"[dim]角色:{chars} 规则:{rules} 卷:{vols}[/dim]")
            print_success("凝练完成")
        except Exception as e:
            print_error(f"凝练失败: {e}")
            raise

    # ===== Writing =====

    def _write_all_volumes(self):
        console.print()
        mode = "极速（无审阅）" if self.fast_mode else f"{self.review_rounds}轮审阅"
        console.print(f"[bold yellow]━━━ 3+. 写作 ({mode}) ━━━[/bold yellow]")
        total_chapters = sum(len(v.chapters) for v in self.project.volumes)
        total_volumes = len(self.project.volumes)
        total_target = sum(
            c.word_count_target for v in self.project.volumes for c in v.chapters
        )
        console.print(f"[bold]《{self.project.title}》[/bold] {total_volumes}卷 {total_chapters}章 目标约{total_target}字\n")

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
            must_happen = ch_plan.get("must_happen", chapter.synopsis)
            pov = ch_plan.get("pov", chapter.pov_character)
            prev = self._get_prev_context(vi, ci)
            self._write_and_review_one(vi, ci, chapter, volume_goal, must_happen, pov, prev)
            self._save_project()

        volume.status = "done"

    async def _write_volumes_parallel(self):
        pending = [vi for vi, v in enumerate(self.project.volumes)
                   if any(c.status == "pending" for c in v.chapters)]
        n = min(len(pending), 5)
        console.print(f"[dim]{n} 个子代理各负责一卷，并行写作...[/dim]\n")

        async def write_one_volume(vi):
            volume = self.project.volumes[vi]
            vol_plan = self.brief.get("volume_plan", [])
            vol_brief = vol_plan[vi] if vi < len(vol_plan) else {}
            volume_goal = vol_brief.get("goal", volume.synopsis)

            console.print(f"[cyan]📖 第{volume.volume_number}卷「{volume.volume_title}」开始[/cyan]")
            for ci, chapter in enumerate(volume.chapters):
                if chapter.status == "done":
                    continue
                ch_brief = vol_brief.get("chapters", [])
                ch_plan = ch_brief[ci] if ci < len(ch_brief) else {}
                must_happen = ch_plan.get("must_happen", chapter.synopsis)
                pov = ch_plan.get("pov", chapter.pov_character)
                prev = self._get_prev_context(vi, ci)
                await asyncio.to_thread(
                    self._write_and_review_one, vi, ci, chapter, volume_goal, must_happen, pov, prev
                )
                self._save_project()
            volume.status = "done"
            console.print(f"[green]✅ 第{volume.volume_number}卷完成[/green]")

        batch_size = min(5, len(pending))
        for i in range(0, len(pending), batch_size):
            batch = pending[i : i + batch_size]
            await asyncio.gather(*(write_one_volume(vi) for vi in batch))

    def _write_and_review_one(self, vi, ci, chapter, volume_goal, must_happen, pov, prev):
        volume = self.project.volumes[vi]
        target = chapter.word_count_target
        progress = f"{chapter.chapter_number}/{len(volume.chapters)}"
        console.print(f"\n[bold cyan]第{chapter.chapter_number}章「{chapter.chapter_title}」({progress}) 目标{target}字[/bold cyan]")
        console.print(f"[dim]{must_happen}[/dim]\n")

        # --- Write with expansion ---
        try:
            writer = self.orchestrator._get_writer()
            _, resolve_fs = self.orchestrator.get_foreshadowing_context(
                self.project, volume.volume_number, chapter.chapter_number
            )
            bible_ctx = self.orchestrator.get_bible_context(
                self.project, volume.volume_number, chapter.chapter_number
            )

            # First pass
            content = ""
            for chunk in writer.write_chapter_stream(
                brief=self.brief or {},
                volume_number=volume.volume_number, volume_title=volume.volume_title,
                volume_goal=volume_goal, chapter_number=chapter.chapter_number,
                chapter_title=chapter.chapter_title, must_happen=must_happen, pov=pov,
                previous_context=prev,
                plant_foreshadowing="根据大纲自然植入选定的伏笔",
                resolve_foreshadowing=resolve_fs, bible_context=bible_ctx,
            ):
                content += chunk
                print_streaming(chunk)
            word_count = len(content)
            console.print(f"\n[dim]初稿: {word_count} 字 (目标 {target})[/dim]")

            # Auto-expand if too short (below 70% of target)
            expand_count = 0
            max_expands = 3
            while word_count < target * 0.7 and expand_count < max_expands:
                expand_count += 1
                shortage = target - word_count
                console.print(f"[yellow]⚠ 字数不足 ({word_count}/{target})，自动扩展第{expand_count}次...[/yellow]\n")
                expansion = ""
                for chunk in writer.write_chapter_stream(
                    brief=self.brief or {},
                    volume_number=volume.volume_number, volume_title=volume.volume_title,
                    volume_goal=volume_goal, chapter_number=chapter.chapter_number,
                    chapter_title=chapter.chapter_title,
                    must_happen=f"扩展本章内容到{target}字。保持已有内容不变，增加细节描写、对话、场景。当前{word_count}字，需增加约{shortage}字。",
                    pov=pov, previous_context=content[-500:],
                    plant_foreshadowing="", resolve_foreshadowing="",
                    bible_context=bible_ctx,
                ):
                    expansion += chunk
                    print_streaming(chunk)
                content += "\n" + expansion
                word_count = len(content)

            chapter.content = content
            r = "✅" if word_count >= target * 0.7 else "⚠"
            console.print(f"\n[green]{r} 完成 ({word_count} 字)[/green]")

            with self._lock:
                self.project.bible.establish("plot", f"V{volume.volume_number}C{chapter.chapter_number}.synopsis",
                                             chapter.synopsis, volume.volume_number, chapter.chapter_number)

        except Exception as e:
            print_error(f"写作失败: {e}")
            chapter.status = "pending"
            return

        # --- Review + Revise ---
        if not self.fast_mode:
            chapter.status = "reviewing"
            self._review_revise_loop(vi, ci, chapter)
        chapter.status = "done"

    def _review_revise_loop(self, vi, ci, chapter):
        if self.review_rounds <= 0:
            return

        for round_num in range(1, self.review_rounds + 1):
            console.print()
            console.print(f"[bold red]🔍 编辑审阅 (第{round_num}轮)[/bold red]")

            report = ""
            try:
                report = self.orchestrator.review_chapter(self.project, vi, ci, on_chunk=print_streaming)
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
                    brief=self.brief or {},
                    original_content=chapter.content,
                    editor_report=report,
                ):
                    revised += chunk
                    print_streaming(chunk)
                chapter.content = revised
                console.print(f"\n[green]✅ 修改完成 ({len(revised)} 字)[/green]")
            except Exception as e:
                print_warning(f"修改跳过: {e}")
                return

    def _report_has_issues(self, report: str) -> bool:
        if not report.strip():
            return False
        lines = [l.strip() for l in report.split("\n") if l.strip()]
        issue_lines = [l for l in lines if re.search(r'⚠|不合格|必须修改|严重问题|有矛盾|不合理|硬伤', l)]
        if issue_lines:
            return True
        pass_lines = [l for l in lines if re.search(r'通过|无问题|没问题|合格|没有发现|未发现', l)]
        if len(pass_lines) >= len(lines) * 0.5:
            return False
        return bool(report.strip())

    def _get_prev_context(self, vi, ci):
        if ci == 0:
            return ""
        prev = self.project.volumes[vi].chapters[ci - 1]
        if prev.content:
            return f"上一章结尾: ...{prev.content[-300:]}"
        return f"前一章「{prev.chapter_title}」: {prev.synopsis}"

    def _finalize(self):
        console.print()
        console.print("[bold green]━━━ 小说创作完成！━━━[/bold green]")
        self.project.current_stage = "done"
        proj_dir = self.file_manager.save(self.project)

        total_words = sum(len(c.content) for v in self.project.volumes for c in v.chapters)
        total_chapters = sum(len(v.chapters) for v in self.project.volumes)
        total_target = sum(c.word_count_target for v in self.project.volumes for c in v.chapters)
        fs = self.project.foreshadowing.stats()

        console.print(f"\n[bold]《{self.project.title}》[/bold]")
        console.print(f"模版: {self.project.template or '自动'} | {len(self.project.volumes)}卷 {total_chapters}章")
        console.print(f"字数: 约{total_words}字 (目标{total_target}字) | 达标率: {min(100, int(total_words/max(1,total_target)*100))}%")
        console.print(f"伏笔回收: {fs['rate']} | 圣经条目: {self.project.bible.stats()['total']}")
        console.print(f"\n[cyan]已保存: {proj_dir}[/cyan]")
        for f in sorted(proj_dir.rglob("*.md")):
            console.print(f"  [dim]{f.relative_to(proj_dir)}[/dim]")
        console.print(f"\n[dim]输入新灵感开始下一篇，/quit 退出[/dim]")

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
