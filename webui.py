#!/usr/bin/env python3
"""DeepSeek Writer — 完整 Web 界面 (Gradio)。

全功能: 配置 → 大纲 → 人物 → 写作 → 审阅 → 导出
"""

from __future__ import annotations
import asyncio
import sys
import re
import threading
from typing import Generator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# ── Monkey-patch: fix gradio 4.44.1 + gradio_client 1.3.0 schema bug ──
def _patch_gradio_client():
    """Fix TypeError in get_type() when schema is a boolean (valid JSON Schema)."""
    try:
        import gradio_client.utils as gcu
        _orig_get_type = gcu.get_type
        _orig_json_schema = gcu._json_schema_to_python_type

        def _fixed_get_type(schema):
            if isinstance(schema, bool):
                return "boolean"  # True schema = any type, map to bool as safest fallback
            return _orig_get_type(schema)

        def _fixed_json_schema_to_python_type(schema, defs):
            if isinstance(schema, bool):
                return "Any"
            return _orig_json_schema(schema, defs)

        gcu.get_type = _fixed_get_type
        gcu._json_schema_to_python_type = _fixed_json_schema_to_python_type
    except Exception:
        pass

_patch_gradio_client()
# ────────────────────────────────────────────────────────────────

from config import Config
from orchestrator import Orchestrator
from project import Project, Volume, Chapter
from utils.file_manager import FileManager
from utils.exporter import Exporter
from utils.memory import MemoryStore
from templates import list_templates, get_template, template_to_prompt


# ──────────────────────────────────────────────
# CSS / custom styling
# ──────────────────────────────────────────────

CUSTOM_CSS = """
.gradio-container { max-width: 1200px !important; }
.header-title { text-align: center; margin-bottom: 0.5em; }
.stage-box { border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin: 8px 0; }
.character-card { border-left: 3px solid #667eea; padding: 8px 12px; margin: 6px 0; background: #f8f9fa; border-radius: 4px; }
.chapter-done { color: #22c55e; }
.chapter-pending { color: #9ca3af; }
.chapter-reviewing { color: #f59e0b; }
.log-line { font-family: monospace; font-size: 0.85em; padding: 2px 0; border-bottom: 1px solid #eee; }
.download-btn { margin: 4px; }
.export-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
"""


# ──────────────────────────────────────────────
# Helper: background task runner
# ──────────────────────────────────────────────

def _run_async(coro):
    """Safely run an async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in event loop — create a new one in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ──────────────────────────────────────────────
# WebApp
# ──────────────────────────────────────────────

class WebApp:
    def __init__(self):
        self.config = Config.load()
        self.orchestrator = Orchestrator(self.config)
        self.file_manager = FileManager()
        self.project: Project | None = None
        self.brief: dict | None = None
        self.memory: MemoryStore | None = None
        self.logs: list[str] = []
        self._lock = threading.Lock()
        self._stream_buffer: list[str] = []
        self.auto_review = True      # 全自动三编辑审阅
        self.review_rounds = 2       # 审阅轮数
        self.parallel_writers = True # 多子代理并行写作
        self.num_scenes = 3          # 每章拆成几段

    # ── Logging ──

    def log(self, msg: str):
        self.logs.append(msg)
        if len(self.logs) > 200:
            self.logs = self.logs[-100:]

    def get_logs(self, n: int = 30) -> str:
        return "\n".join(self.logs[-n:])

    def clear_logs(self) -> str:
        self.logs.clear()
        return ""

    # ── Config ──

    def set_api(self, provider: str, api_key: str, model: str) -> str:
        self.config.provider = provider
        if provider == "deepseek":
            self.config.deepseek_api_key = api_key
            self.config.model = model
        else:
            self.config.claude_api_key = api_key
            self.config.claude_model = model
        self.config.save()
        self.orchestrator = Orchestrator(self.config)
        self.log(f"已配置: {provider} — {model}")
        return f"✅ 已配置: {provider} — {model}"

    def get_config_status(self) -> str:
        key_ok = bool(self.config.api_key)
        return f"提供商: {self.config.provider} | 模型: {self.config.active_model} | API Key: {'已设置' if key_ok else '❌ 未设置'}"

    # ── Project creation ──

    def create_project(self, idea: str, template_name: str, user_suggestions: str = "") -> tuple[str, str]:
        """Generate outline + characters. Returns (status_md, logs)."""
        if not self.config.api_key:
            return "❌ 请先在「配置」标签设置 API Key", self.get_logs()

        self.log(f"📝 创建项目: {idea[:60]}...")
        self.project = Project(premise=idea)
        self.brief = None
        self.memory = MemoryStore("")

        # Template
        template = None
        if template_name and template_name != "自动":
            tmpl = get_template(template_name)
            if tmpl:
                template = {"name": template_name, **tmpl}

        # Stage 1: Outline
        self.log("📋 生成大纲...")
        if self.config.search_enabled:
            self.log("🌐 联网搜索背景信息...")
        try:
            template_guide = template_to_prompt(template) if template else ""
            outline = self.orchestrator.generate_outline(
                premise=idea,
                template_guide=template_guide,
                user_suggestions=user_suggestions,
            )
            self._load_outline(outline)
            vols = len(self.project.volumes)
            chs = sum(len(v.chapters) for v in self.project.volumes)
            self.log(f"✅ 大纲: 《{self.project.title}》({self.project.genre}) {vols}卷 {chs}章")
        except Exception as e:
            self.log(f"❌ 大纲失败: {e}")
            return f"❌ 大纲生成失败: {e}", self.get_logs()

        # Stage 2: Characters
        self.log("👤 设计人物...")
        try:
            chars = self.orchestrator.design_characters(outline=self.project.to_dict(), style="自动匹配")
            self._load_characters(chars)
            char_count = len(chars.get("characters", []))
            self.log(f"✅ 人物: {char_count} 个")
        except Exception as e:
            self.log(f"❌ 人物设计失败: {e}")
            return f"❌ 人物设计失败: {e}", self.get_logs()

        # Stage 2.5: Condense
        self.log("📐 凝练写作指南...")
        try:
            self.brief = self.orchestrator.condense(
                outline=self.project.to_dict(),
                characters=self.project.characters,
                writing_style=self.project.writing_style,
            )
            self.log("✅ 凝练完成，可以开始写作")
        except Exception as e:
            self.log(f"❌ 凝练失败: {e}")
            return self._status_md(), self.get_logs()

        # Init memory
        if self.memory:
            self.memory.project_name = self.project.title
            for c in chars.get("characters", []):
                self.memory.add_character_fact(c.get("name", ""), c.get("personality", ""))
            for rule in chars.get("world_building", {}).get("rules", []):
                self.memory.add_world_rule(rule)

        self.file_manager.save(self.project)
        return self._status_md(), self.get_logs()

    def _load_outline(self, outline: dict):
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
                volume.chapters.append(Chapter(
                    chapter_number=c["chapter_number"],
                    chapter_title=c["chapter_title"],
                    synopsis=c["synopsis"],
                    key_events=c.get("key_events", []),
                    pov_character=c.get("pov_character", ""),
                    word_count_target=min(c.get("word_count_target", 3000), 3000),
                ))
            self.project.volumes.append(volume)
        self.project.current_stage = "outlined"

    def _load_characters(self, chars: dict):
        self.project.characters = chars
        self.project.plot_arcs = chars.get("plot_arcs", {})
        self.project.world_building = chars.get("world_building", {})
        self.project.writing_style = chars.get("writing_style", {})
        self.project.style_reference = chars.get("style_reference", {})
        self.project.current_stage = "characters_done"
        for c in chars.get("characters", []):
            self.project.bible.establish("character", f"{c['name']}.role", c.get("role", ""), 0, 0)
            self.project.bible.establish("character", f"{c['name']}.personality", c.get("personality", ""), 0, 0)
        for rule in chars.get("world_building", {}).get("rules", []):
            self.project.bible.establish("world", f"rule.{rule[:30]}", rule, 0, 0)

    # ── Status display ──

    def _status_md(self) -> str:
        if not self.project:
            return "### 暂无项目\n输入创意并点击「生成大纲+人物」开始创作。"
        vols = len(self.project.volumes)
        total_ch = sum(len(v.chapters) for v in self.project.volumes)
        done_ch = sum(1 for v in self.project.volumes for c in v.chapters if c.status == "done")
        total_words = sum(len(c.content) for v in self.project.volumes for c in v.chapters)
        total_target = sum(c.word_count_target for v in self.project.volumes for c in v.chapters)
        pct = f"{done_ch / total_ch * 100:.0f}%" if total_ch > 0 else "0%"

        lines = [
            f"## 📖 《{self.project.title}》",
            f"**类型**: {self.project.genre} | **主题**: {self.project.theme}",
            f"**基调**: {self.project.tone}",
            f"**梗概**: {self.project.premise}",
            "",
            f"**进度**: {done_ch}/{total_ch} 章 ({pct}) | **字数**: 约{total_words} / 目标{total_target}",
            "",
        ]

        # Volume & chapter table
        lines.append("| 卷 | 章 | 标题 | 状态 | 字数 |")
        lines.append("|---|---|---|---|---|")
        for vol in self.project.volumes:
            for ch in vol.chapters:
                status_icon = {"pending": "⏳", "writing": "✍️", "done": "✅", "reviewing": "🔍"}.get(ch.status, ch.status)
                wc = len(ch.content) if ch.content else 0
                lines.append(
                    f"| 第{vol.volume_number}卷 | 第{ch.chapter_number}章 | {ch.chapter_title} "
                    f"| {status_icon} | {wc} |"
                )
        return "\n".join(lines)

    def get_status(self) -> str:
        return self._status_md()

    # ── Outline display ──

    def get_outline_view(self) -> str:
        if not self.project:
            return "暂无项目"
        lines = [f"## 📋 《{self.project.title}》大纲", ""]
        for vol in self.project.volumes:
            lines.append(f"### 第{vol.volume_number}卷「{vol.volume_title}」")
            lines.append(f"_{vol.synopsis}_")
            lines.append("")
            for ch in vol.chapters:
                events = "、".join(ch.key_events[:3]) if ch.key_events else ch.synopsis[:60]
                lines.append(f"- **第{ch.chapter_number}章「{ch.chapter_title}」** — {events}")
            lines.append("")
        return "\n".join(lines)

    # ── Character display ──

    def get_character_view(self) -> str:
        if not self.project or not self.project.characters:
            return "暂无人物设定"
        chars = self.project.characters
        lines = ["## 👤 人物档案", ""]
        for c in chars.get("characters", []):
            lines.append(f"### {c.get('name','')}（{c.get('role','')}）")
            lines.append(f"- **年龄**: {c.get('age','')} | **外貌**: {c.get('appearance','')}")
            lines.append(f"- **性格**: {c.get('personality','')}")
            lines.append(f"- **背景**: {c.get('background','')}")
            lines.append(f"- **动机**: {c.get('motivation','')}")
            lines.append(f"- **弧线**: {c.get('arc','')}")
            speech = c.get("speech_style", "")
            if speech:
                lines.append(f"- **说话方式**: {speech}")
            quirks = c.get("quirks", [])
            if quirks:
                lines.append(f"- **特征**: {', '.join(quirks)}")
            lines.append("")

        ws = chars.get("writing_style", {})
        if ws:
            lines.append("### ✍️ 写作风格")
            for k, v in ws.items():
                if not isinstance(v, list):
                    lines.append(f"- **{k}**: {v}")
                else:
                    lines.append(f"- **{k}**: {', '.join(v)}")
        return "\n".join(lines)

    # ── Writing ──

    def write_all_chapters(self, textarea_user_suggestions: str = "", progress=...) -> Generator[tuple[str, str], None, tuple[str, str]]:  # type: ignore
        """全自动写作：各卷并行，卷内顺序。"""
        if not self.project or not self.brief:
            yield self._status_md(), self.get_logs()
            return

        self.writing_suggestions = textarea_user_suggestions

        total_pending = sum(
            1 for v in self.project.volumes for c in v.chapters if c.status == "pending"
        )
        if total_pending == 0:
            self.log("所有章节已完成！")
            yield self._status_md(), self.get_logs()
            return

        review_mode = "三编辑并审" if self.auto_review else "跳过审阅"
        self.log(f"✍️ 开始全自动写作 {total_pending} 章 ({review_mode}, {self.review_rounds}轮)，各卷并行...")
        if self.config.search_enabled:
            self.log("🌐 已开启联网搜索，写作时将自动检索相关信息")
        yield self._status_md(), self.get_logs()
        self.project.current_stage = "writing"

        import concurrent.futures
        import threading
        _log_lock = threading.Lock()

        def _safe_log(msg: str):
            with _log_lock:
                self.log(msg)

        def _write_volume(vi: int, volume) -> int:
            """写入单卷所有未完成章节，返回本卷完成章数。"""
            vol_plan = self.brief.get("volume_plan", [])
            vol_brief = vol_plan[vi] if vi < len(vol_plan) else {}
            volume_goal = vol_brief.get("goal", volume.synopsis)
            vol_done = 0

            for ci, chapter in enumerate(volume.chapters):
                if chapter.status == "done":
                    continue

                ch_brief = vol_brief.get("chapters", [])
                ch_plan = ch_brief[ci] if ci < len(ch_brief) else {}
                must_happen = ch_plan.get("must_happen", chapter.synopsis)
                pov = ch_plan.get("pov", chapter.pov_character)
                prev = self._prev_context(vi, ci)

                _safe_log(f"✍️ V{volume.volume_number}C{chapter.chapter_number}「{chapter.chapter_title}」(子代理#{vi+1})...")

                try:
                    writer = self.orchestrator._get_writer(volume_idx=vi)
                    _, resolve_fs = self.orchestrator.get_foreshadowing_context(
                        self.project, volume.volume_number, chapter.chapter_number)
                    bible_ctx = self.orchestrator.get_bible_context(
                        self.project, volume.volume_number, chapter.chapter_number)

                    mem_ctx = ""
                    if self.memory:
                        mem_ctx = self.memory.get_context_for_chapter(
                            volume.volume_number, chapter.chapter_number, must_happen)

                    # 联网搜索本章相关背景
                    search_ctx = ""
                    if self.config.search_enabled:
                        _safe_log(f"  🌐 搜索 «{chapter.chapter_title}» 相关背景...")
                        search_ctx = self.orchestrator._do_search(
                            f"{self.project.title} {chapter.chapter_title} {chapter.synopsis}"
                        )

                    if self.parallel_writers and not getattr(self, '_first_write_done', False):
                        _safe_log(f"  🧩 多子代理并行写作({self.num_scenes}个场景)...")
                        content = writer.write_parallel(
                            brief=self.brief,
                            volume_number=volume.volume_number,
                            volume_title=volume.volume_title,
                            volume_goal=volume_goal,
                            chapter_number=chapter.chapter_number,
                            chapter_title=chapter.chapter_title,
                            must_happen=must_happen,
                            pov=pov,
                            previous_context=prev,
                            search_context=search_ctx,
                            user_suggestions=self.writing_suggestions,
                            bible_context=bible_ctx + "\n" + mem_ctx,
                            num_scenes=self.num_scenes,
                        )
                    else:
                        content = writer.write_chapter(
                            brief=self.brief,
                            volume_number=volume.volume_number,
                            volume_title=volume.volume_title,
                            volume_goal=volume_goal,
                            chapter_number=chapter.chapter_number,
                            chapter_title=chapter.chapter_title,
                            must_happen=must_happen,
                            pov=pov,
                            previous_context=prev,
                            plant_foreshadowing="自然植入大纲中的伏笔",
                            resolve_foreshadowing=resolve_fs,
                            bible_context=bible_ctx + "\n" + mem_ctx,
                            search_context=search_ctx,
                            user_suggestions=self.writing_suggestions,
                        )

                    # Auto-expand
                    wc = len(content)
                    target = chapter.word_count_target
                    expand_count = 0
                    while wc < target * 0.7 and expand_count < 3:
                        expand_count += 1
                        shortage = target - wc
                        self.log(f"  ⚠ 扩展第{expand_count}次 (缺{shortage}字)...")
                        expansion = writer.write_chapter(
                            brief=self.brief,
                            volume_number=volume.volume_number,
                            volume_title=volume.volume_title,
                            volume_goal=volume_goal,
                            chapter_number=chapter.chapter_number,
                            chapter_title=chapter.chapter_title,
                            must_happen=f"扩展本章到{target}字。保留已有内容，增加细节。需增加约{shortage}字。",
                            pov=pov,
                            previous_context=content[-500:],
                            plant_foreshadowing="",
                            resolve_foreshadowing="",
                            bible_context="",
                        )
                        content += "\n" + expansion
                        wc = len(content)

                    chapter.content = content
                    _safe_log(f"  📝 初稿 {wc} 字")

                    # ── Auto Review + Revise ──
                    if self.auto_review:
                        for round_num in range(1, self.review_rounds + 1):
                            _safe_log(f"  🔍 三编辑并审 第{round_num}轮...")
                            try:
                                report = self.orchestrator.review_chapter(
                                    self.project, vi, ci, self.brief,
                                    parallel=True,
                                )
                            except Exception as e:
                                _safe_log(f"  ⚠ 审阅跳过: {e}")
                                break

                            if not self._report_has_real_issues(report):
                                _safe_log(f"  ✅ 编辑: 无重大问题，通过")
                                break

                            issue_count = len(re.findall(r'⚠|需修改|矛盾|问题', report))
                            _safe_log(f"  ⚠ 发现 {issue_count} 处问题，自动修改...")

                            try:
                                revised = writer.revise_chapter(
                                    brief=self.brief,
                                    original_content=chapter.content,
                                    editor_report=report,
                                )
                                chapter.content = revised
                                _safe_log(f"  ✅ 第{round_num}轮修改完成 ({len(revised)} 字)")
                            except Exception as e:
                                _safe_log(f"  ⚠ 修改跳过: {e}")
                                break
                    else:
                        _safe_log(f"  ⏩ 跳过审阅 (极速模式)")

                    chapter.status = "done"
                    vol_done += 1

                    # Update bible
                    with self._lock:
                        self.project.bible.establish(
                            "plot", f"V{volume.volume_number}C{chapter.chapter_number}.synopsis",
                            chapter.synopsis, volume.volume_number, chapter.chapter_number)

                    # Memory
                    if self.memory:
                        self.memory.add_chapter_summary(
                            volume.volume_number, chapter.chapter_number,
                            chapter.synopsis, pov, ", ".join(chapter.key_events[:3]))

                    _safe_log(f"  🎉 第{chapter.chapter_number}章完成 ({len(chapter.content)} 字)")

                except Exception as e:
                    _safe_log(f"  ❌ V{volume.volume_number}第{chapter.chapter_number}章失败: {e}")
                    chapter.status = "pending"
                    continue

                # Save after each chapter
                with _log_lock:
                    self.file_manager.save(self.project)

            volume.status = "done"
            return vol_done

        # 各卷并行提交
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.project.volumes)) as pool:
            vol_futures = {
                pool.submit(_write_volume, vi, volume): vi
                for vi, volume in enumerate(self.project.volumes)
            }
            done_count = 0
            for future in concurrent.futures.as_completed(vol_futures):
                vi = vol_futures[future]
                try:
                    vol_done = future.result(timeout=3600)
                    done_count += vol_done
                    _safe_log(f"📚 第{vi+1}卷完成 ({vol_done}章)")
                except Exception as e:
                    _safe_log(f"❌ 第{vi+1}卷写入异常: {e}")
                yield self._status_md(), self.get_logs()

        self.project.current_stage = "done"
        self.file_manager.save(self.project)
        self.log(f"🎉 全自动写作完成！共 {done_count} 章")
        yield self._status_md(), self.get_logs()

    def _report_has_real_issues(self, report: str) -> bool:
        """判断三编辑报告中是否有需要修改的实际问题（跟随严格度）。"""
        if not report or not report.strip():
            return False

        # 从编辑器获取严格度配置
        strict_cfg = self.orchestrator.get_editor_strictness()
        pass_threshold = strict_cfg.get('pass_threshold', 3)
        report_min_len = strict_cfg.get('report_min_len', 60)

        pass_count = len(re.findall(
            r'(逻辑通过|节奏通过|连贯通过|无问题|没问题|合格|未发现问题|没有发现问题|无不一致|无矛盾)',
            report,
        ))
        if pass_count >= pass_threshold:
            return False

        # 有明确的 ⚠ 或问题关键词 → 必须修改
        if re.search(
            r'⚠|不合格|必须修改|严重问题|有矛盾|不合理|硬伤|需修改|建议修改|建议重写|建议调整|'
            r'明显矛盾|严重拖沓|重大漏洞|行为与设定|前后不一|违反|逻辑不通|逻辑错误',
            report,
        ):
            return True

        # 有位编辑提出了具体内容
        if re.search(r'需(修正|调整|改进|重写)|建议(删除|修改|重写|调整)', report):
            return True

        # 删除通过标记后仍有实质性内容（长度门槛跟随严格度）
        body = re.sub(r'(逻辑通过|节奏通过|连贯通过|无问题|合格)', '', report).strip()
        if len(body) > report_min_len:
            return True

        return False

    def write_single_chapter(self, volume_num: int, chapter_num: int) -> tuple[str, str, str]:
        """Write a single chapter, return (content, status, logs)."""
        if not self.project or not self.brief:
            return "", "请先创建项目", self.get_logs()

        for vi, volume in enumerate(self.project.volumes):
            if volume.volume_number == volume_num:
                for ci, chapter in enumerate(volume.chapters):
                    if chapter.chapter_number == chapter_num:
                        break
                else:
                    return "", f"未找到第{chapter_num}章", self.get_logs()
                break
        else:
            return "", f"未找到第{volume_num}卷", self.get_logs()

        vol_plan = self.brief.get("volume_plan", [])
        vol_brief = vol_plan[vi] if vi < len(vol_plan) else {}
        volume_goal = vol_brief.get("goal", volume.synopsis)
        ch_brief = vol_brief.get("chapters", [])
        ch_plan = ch_brief[ci] if ci < len(ch_brief) else {}
        must_happen = ch_plan.get("must_happen", chapter.synopsis)
        pov = ch_plan.get("pov", chapter.pov_character)
        prev = self._prev_context(vi, ci)

        self.log(f"✍️ 第{chapter_num}章「{chapter.chapter_title}」(子代理#{vi+1})...")

        try:
            writer = self.orchestrator._get_writer(volume_idx=vi)
            _, resolve_fs = self.orchestrator.get_foreshadowing_context(
                self.project, volume.volume_number, chapter.chapter_number)
            bible_ctx = self.orchestrator.get_bible_context(
                self.project, volume.volume_number, chapter.chapter_number)

            # 联网搜索本章相关背景
            search_ctx = ""
            if self.config.search_enabled:
                self.log(f"  🌐 搜索 «{chapter.chapter_title}» 相关背景...")
                search_ctx = self.orchestrator._do_search(
                    f"{self.project.title} {chapter.chapter_title} {chapter.synopsis}"
                )

            if self.parallel_writers:
                self.log(f"  🧩 多子代理并行写作({self.num_scenes}个场景)...")
                content = writer.write_parallel(
                    brief=self.brief,
                    volume_number=volume.volume_number,
                    volume_title=volume.volume_title,
                    volume_goal=volume_goal,
                    chapter_number=chapter.chapter_number,
                    chapter_title=chapter.chapter_title,
                    must_happen=must_happen, pov=pov,
                    previous_context=prev,
                    bible_context=bible_ctx,
                    search_context=search_ctx,
                    user_suggestions=getattr(self, 'writing_suggestions', ''),
                    num_scenes=self.num_scenes,
                )
            else:
                content = writer.write_chapter(
                    brief=self.brief,
                    volume_number=volume.volume_number,
                    volume_title=volume.volume_title,
                    volume_goal=volume_goal,
                    chapter_number=chapter.chapter_number,
                    chapter_title=chapter.chapter_title,
                    must_happen=must_happen, pov=pov,
                    previous_context=prev,
                    plant_foreshadowing="自然植入",
                    resolve_foreshadowing=resolve_fs,
                    bible_context=bible_ctx,
                    search_context=search_ctx,
                    user_suggestions=getattr(self, 'writing_suggestions', ''),
                )
            chapter.content = content
            chapter.status = "done"
            self.file_manager.save(self.project)
            self.log(f"  ✅ ({len(content)} 字)")
            return content, self._status_md(), self.get_logs()
        except Exception as e:
            self.log(f"  ❌ {e}")
            return "", f"❌ {e}", self.get_logs()

    def _prev_context(self, vi: int, ci: int) -> str:
        if ci == 0:
            return ""
        prev = self.project.volumes[vi].chapters[ci - 1]
        if prev.content:
            return f"上一章结尾: ...{prev.content[-300:]}"
        return f"前一章「{prev.chapter_title}」: {prev.synopsis}"

    # ── Review / Edit ──

    def review_chapter(self, volume_num: int, chapter_num: int) -> str:
        """Review a single chapter, return review report."""
        if not self.project:
            return "暂无项目"

        for vi, volume in enumerate(self.project.volumes):
            if volume.volume_number == volume_num:
                for ci, chapter in enumerate(volume.chapters):
                    if chapter.chapter_number == chapter_num:
                        break
                else:
                    return f"未找到第{chapter_num}章"
                break
        else:
            return f"未找到第{volume_num}卷"

        if not chapter.content:
            return "该章节尚未写作"

        self.log(f"🔍 审阅第{chapter_num}章...")
        try:
            report = self.orchestrator.review_chapter(
                self.project, vi, ci, self.brief or {}, parallel=True,
            )
            return report
        except Exception as e:
            return f"审阅失败: {e}"

    def revise_chapter(self, volume_num: int, chapter_num: int, editor_report: str) -> tuple[str, str]:
        """Revise chapter based on report, returns (new_content, logs)."""
        if not self.project:
            return "", "暂无项目"

        for volume in self.project.volumes:
            if volume.volume_number == volume_num:
                for chapter in volume.chapters:
                    if chapter.chapter_number == chapter_num:
                        break
                else:
                    return "", f"未找到第{chapter_num}章"
                break
        else:
            return "", f"未找到第{volume_num}卷"

        self.log(f"✏️ 修改第{chapter_num}章...")
        try:
            writer = self.orchestrator._get_writer()
            revised = writer.revise_chapter(
                brief=self.brief or {},
                original_content=chapter.content,
                editor_report=editor_report,
            )
            chapter.content = revised
            self.file_manager.save(self.project)
            self.log(f"  ✅ 修改完成 ({len(revised)} 字)")
            return revised, self.get_logs()
        except Exception as e:
            return chapter.content, f"修改失败: {e}"

    # ── Project management ──

    def load_project(self, name: str) -> tuple[str, str]:
        proj = self.file_manager.load(name)
        if proj:
            self.project = proj
            self.brief = None
            self.memory = MemoryStore(proj.title)
            self.log(f"📂 已加载「{proj.title}」")
            return self._status_md(), self.get_logs()
        self.log(f"❌ 未找到: {name}")
        return f"❌ 未找到: {name}", self.get_logs()

    def list_saved(self) -> str:
        projects = self.file_manager.list_projects()
        if not projects:
            return "(无已保存项目)"
        return "\n".join(f"- {p}" for p in sorted(projects))

    def delete_project(self, name: str) -> str:
        try:
            self.file_manager.delete_project(name)
            if self.project and self.project.title == name:
                self.project = None
                self.brief = None
            self.log(f"🗑 已删除: {name}")
            return f"✅ 已删除: {name}"
        except Exception as e:
            return f"❌ {e}"

    # ── Chapter reading ──

    def get_chapter_content(self, volume_num: int, chapter_num: int) -> str:
        if not self.project:
            return "暂无项目"
        for v in self.project.volumes:
            if v.volume_number == volume_num:
                for c in v.chapters:
                    if c.chapter_number == chapter_num:
                        return c.content or "(本章尚未写作)"
        return "(未找到该章节)"

    def get_volume_chapter_list(self) -> tuple:
        """Returns (volume_dropdown_choices, chapter_dropdown_choices) for the current project."""
        if not self.project:
            return [], []
        vol_choices = [f"第{v.volume_number}卷「{v.volume_title}」" for v in self.project.volumes]
        ch_choices = []
        for v in self.project.volumes:
            for c in v.chapters:
                status = "✅" if c.content else "⏳"
                ch_choices.append(f"{status} 第{v.volume_number}卷第{c.chapter_number}章「{c.chapter_title}」")
        return vol_choices, ch_choices

    # ── Export ──

    def export_format(self, fmt: str) -> tuple[str, str]:
        """Export project in given format. Returns (path, message)."""
        if not self.project:
            return "", "❌ 请先创建或加载项目"
        try:
            exp = Exporter(self.project)
            methods = {
                "md": exp.export_markdown,
                "txt": exp.export_txt,
                "epub": exp.export_epub,
                "pdf": exp.export_pdf,
                "docx": exp.export_docx,
            }
            if fmt in methods:
                path = methods[fmt]()
                self.log(f"📥 导出 {fmt.upper()}: {path}")
                return path, f"✅ 导出成功: {Path(path).name}"
            return "", f"不支持格式: {fmt}"
        except Exception as e:
            return "", f"❌ 导出失败: {e}"

    def export_all_formats(self) -> str:
        """Export all formats, return summary."""
        if not self.project:
            return "❌ 请先创建或加载项目"
        try:
            exp = Exporter(self.project)
            results = exp.export_all()
            lines = ["## 📥 导出结果", ""]
            for fmt, path in results.items():
                if "需要" in path or "跳过" in path:
                    lines.append(f"- **{fmt.upper()}**: {path}")
                else:
                    lines.append(f"- **{fmt.upper()}**: ✅ `{path}`")
            self.log("📥 全格式导出完成")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ {e}"

    # ── Stats ──

    def get_stats(self) -> str:
        if not self.project:
            return "暂无项目"
        total_words = sum(len(c.content) for v in self.project.volumes for c in v.chapters)
        total_ch = sum(len(v.chapters) for v in self.project.volumes)
        done_ch = sum(1 for v in self.project.volumes for c in v.chapters if c.status == "done")
        fs = self.project.foreshadowing.stats()
        bs = self.project.bible.stats()

        lines = [
            f"## 📊 《{self.project.title}》统计",
            "",
            f"| 指标 | 值 |",
            f"|---|---|",
            f"| 卷数 | {len(self.project.volumes)} |",
            f"| 总章节 | {total_ch} |",
            f"| 已完成 | {done_ch} |",
            f"| 总字数 | 约{total_words} |",
            f"| 伏笔总数 | {fs['total']} |",
            f"| 已回收 | {fs['resolved']} ({fs['rate']}) |",
            f"| 关键未收 | {fs['critical_unresolved']} |",
            f"| 圣经条目 | {bs['total']} |",
        ]
        if self.memory:
            ms = self.memory.stats()
            lines.append(f"| 记忆 | {ms['backend']} {ms['count']}条 |")
        return "\n".join(lines)

    # ── Import ──

    def import_constraints(self, file_obj) -> str:
        """Import character/world constraints from uploaded file."""
        if file_obj is None:
            return "请上传文件"
        try:
            # Gradio passes file path or bytes
            if isinstance(file_obj, str):
                content = Path(file_obj).read_text(encoding="utf-8")
            else:
                content = file_obj.decode("utf-8") if isinstance(file_obj, bytes) else str(file_obj)
            self._imported_constraints = content[:3000]
            self.log(f"📥 导入约束文件 ({len(content)} 字)")
            return f"✅ 已导入 ({len(content)} 字)\n\n前3000字将作为人物设计约束:\n{content[:500]}..."
        except Exception as e:
            return f"❌ 导入失败: {e}"


# ──────────────────────────────────────────────
# build_ui — the complete Gradio interface
# ──────────────────────────────────────────────

def build_ui():
    try:
        import gradio as gr
    except ImportError:
        print("需要安装: pip install gradio")
        return

    app = WebApp()

    with gr.Blocks(
        title="DeepSeek Writer — AI 写作助手",
        css=CUSTOM_CSS,
        theme=gr.themes.Soft(),
    ) as ui:
        gr.Markdown(
            "# ✍️ DeepSeek Writer — AI 写作助手",
            elem_classes=["header-title"],
        )

        # ═══════════════════════════════════════
        # Tab 1: Config
        # ═══════════════════════════════════════
        with gr.Tab("⚙️ 配置"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### API 设置")
                    provider = gr.Dropdown(
                        ["deepseek", "claude"],
                        label="提供商",
                        value=app.config.provider,
                    )
                    api_key = gr.Textbox(
                        label="API Key",
                        type="password",
                        value=app.config.api_key,
                        placeholder="输入 API Key...",
                    )
                    from llm.models import DEEPSEEK_MODELS, CLAUDE_MODELS

                    model = gr.Dropdown(
                        list(DEEPSEEK_MODELS.keys()) + list(CLAUDE_MODELS.keys()),
                        label="模型",
                        value=app.config.active_model,
                    )
                    config_btn = gr.Button("💾 保存配置", variant="primary")
                    config_status = gr.Markdown(app.get_config_status())

                with gr.Column(scale=1):
                    gr.Markdown("### 提示")
                    gr.Markdown("""
                    **DeepSeek**: 在 [platform.deepseek.com](https://platform.deepseek.com) 获取 API Key

                    **Claude**: 在 [console.anthropic.com](https://console.anthropic.com) 获取 API Key

                    也可以设置环境变量:
                    - `DEEPSEEK_API_KEY`
                    - `ANTHROPIC_API_KEY`
                    """)

            config_btn.click(
                app.set_api,
                [provider, api_key, model],
                [config_status],
            )

            # Update model choices when provider changes
            def update_models(p):
                if p == "deepseek":
                    return gr.Dropdown(choices=list(DEEPSEEK_MODELS.keys()), value="deepseek-v4-pro")
                return gr.Dropdown(choices=list(CLAUDE_MODELS.keys()), value="claude-sonnet-4-6")

            provider.change(update_models, [provider], [model])

            gr.Markdown("---")
            gr.Markdown("### 🌐 联网搜索")
            with gr.Row():
                search_enabled = gr.Checkbox(label="生成时自动联网搜索", value=app.config.search_enabled,
                                              info="大纲和章节写作前自动搜索相关信息")
                search_provider = gr.Dropdown(["tavily", "searxng"], label="搜索服务",
                                               value=app.config.search_provider)
            with gr.Row():
                tavily_key = gr.Textbox(label="Tavily API Key", type="password",
                                         value=app.config.tavily_api_key,
                                         placeholder="在 tavily.com 获取", scale=2)
                searxng_url = gr.Textbox(label="SearXNG 地址",
                                          value=app.config.searxng_base_url,
                                          placeholder="http://localhost:8888", scale=2)

            def save_search_config(enable, provider, tavily, searxng):
                app.config.search_enabled = enable
                app.config.search_provider = provider
                app.config.tavily_api_key = tavily
                app.config.searxng_base_url = searxng
                app.config.save()
                return f"✅ 搜索配置已保存{'，开启联网' if enable else '，关闭联网'}"

            search_config_btn = gr.Button("💾 保存搜索配置", variant="secondary")
            search_config_status = gr.Markdown("")
            search_config_btn.click(
                save_search_config,
                [search_enabled, search_provider, tavily_key, searxng_url],
                [search_config_status],
            )

        # ═══════════════════════════════════════
        # Tab 2: Create (Outline + Characters)
        # ═══════════════════════════════════════
        with gr.Tab("🎬 创作"):
            with gr.Row():
                with gr.Column(scale=2):
                    gr.Markdown("### 1. 输入创意")
                    idea = gr.Textbox(
                        label="小说创意",
                        placeholder="描述你的故事创意...\n例如: 一个废柴高中生意外获得修仙系统，但系统总让他完成奇怪任务",
                        lines=4,
                    )
                    templates = list_templates()
                    tmpl = gr.Dropdown(
                        ["自动"] + templates,
                        label="写作模版",
                        value="自动",
                    )

                    with gr.Row():
                        create_btn = gr.Button("🎬 生成大纲 + 人物", variant="primary", size="lg")
                        import_file = gr.File(label="导入约束文件 (.md)", file_types=[".md", ".txt"])

                    gr.Markdown("### 💡 写作建议 / 修改要求")
                    user_suggestions = gr.Textbox(
                        label="对 AI 提出的要求",
                        placeholder="例如：参考真实的历史背景来写世界观 / 主角性格参考三国演义中的诸葛亮 / 需要写一些中医相关的知识...",
                        lines=2,
                    )

                with gr.Column(scale=1):
                    gr.Markdown("### 模版说明")
                    tmpl_info = gr.Markdown("选择「自动」让 AI 自动匹配最佳结构")

            def show_template_info(name):
                if not name or name == "自动":
                    return "选择「自动」让 AI 自动匹配最佳结构"
                tmpl_data = get_template(name)
                if not tmpl_data:
                    return "无信息"
                lines = [
                    f"**{name}**: {tmpl_data.get('description','')}",
                    f"适合: {', '.join(tmpl_data.get('best_for',[]))}",
                    f"篇幅: {tmpl_data.get('scale','')}",
                    "",
                    "**弧线**:",
                ]
                for arc in tmpl_data.get("arc_pattern", []):
                    lines.append(f"- {arc['name']}: {arc['purpose']}")
                return "\n".join(lines)

            tmpl.change(show_template_info, [tmpl], [tmpl_info])

            with gr.Row():
                status_md = gr.Markdown("等待输入创意...")
            with gr.Row():
                log_box = gr.Textbox(label="📋 日志", lines=6, interactive=False, autoscroll=True)

            create_btn.click(
                app.create_project,
                [idea, tmpl, user_suggestions],
                [status_md, log_box],
            )

            # Import constraints
            def do_import(file_obj):
                if file_obj is None:
                    return "请先选择文件"
                # Gradio passes the file as a temp path or bytes
                return app.import_constraints(file_obj)

            import_file.change(do_import, [import_file], [log_box])

        # ═══════════════════════════════════════
        # Tab 3: Outline & Characters view
        # ═══════════════════════════════════════
        with gr.Tab("📋 大纲 & 人物"):
            with gr.Row():
                refresh_view_btn = gr.Button("🔄 刷新")
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### 大纲")
                    outline_view = gr.Markdown(app.get_outline_view())
                with gr.Column():
                    gr.Markdown("### 人物")
                    character_view = gr.Markdown(app.get_character_view())

            refresh_view_btn.click(
                lambda: (app.get_outline_view(), app.get_character_view()),
                [],
                [outline_view, character_view],
            )

        # ═══════════════════════════════════════
        # Tab 4: Writing
        # ═══════════════════════════════════════
        with gr.Tab("✍️ 写作"):
            with gr.Row():
                write_status = gr.Markdown(app.get_status())

            with gr.Row():
                with gr.Column(scale=2):
                    write_all_btn = gr.Button("🚀 全自动写作（全部章节）", variant="primary", size="lg")
                with gr.Column(scale=1):
                    parallel_writers_toggle = gr.Checkbox(label="多子代理并行写作", value=True,
                                                          info="多个 AI 子代理同时写不同场景后合并，速度快且内容多元")
                    auto_review_toggle = gr.Checkbox(label="三编辑并审", value=True,
                                                     info="写完后自动三子代理审阅（逻辑+风格+伏笔）")
                    review_rounds_slider = gr.Slider(label="审阅轮数", minimum=1, maximum=3, value=2, step=1,
                                                    info="每章最多审阅修改几轮")
                    strictness_slider = gr.Slider(label="编辑严格度", minimum=1, maximum=5, value=app.config.strictness, step=1,
                                                  info="1=极宽松 → 5=极其严格，影响编辑找茬的敏锐度")

            with gr.Row():
                write_log = gr.Textbox(label="📋 写作日志", lines=8, interactive=False, autoscroll=True)

            labels = {1: '极宽松', 2: '宽松', 3: '适中', 4: '严格', 5: '极其严格'}

            def update_review_settings(parallel, auto, rounds, strictness):
                app.parallel_writers = parallel
                app.auto_review = auto
                app.review_rounds = int(rounds)
                app.config.strictness = int(strictness)
                app.config.save()
                app.orchestrator = Orchestrator(app.config)
                s_label = labels.get(int(strictness), '适中')
                return f"写作: {'多代理并行' if parallel else '单代理'} | 审阅: {'三编辑并审' if auto else '跳过'} | {int(rounds)}轮 | 严格度{int(strictness)}/5({s_label})"

            parallel_writers_toggle.change(update_review_settings, [parallel_writers_toggle, auto_review_toggle, review_rounds_slider, strictness_slider], None)
            auto_review_toggle.change(update_review_settings, [parallel_writers_toggle, auto_review_toggle, review_rounds_slider, strictness_slider], None)
            review_rounds_slider.change(update_review_settings, [parallel_writers_toggle, auto_review_toggle, review_rounds_slider, strictness_slider], None)
            strictness_slider.change(update_review_settings, [parallel_writers_toggle, auto_review_toggle, review_rounds_slider, strictness_slider], None)

            gr.Markdown("### 💡 用户修改建议")
            writing_suggestions = gr.Textbox(
                label="对当前写作的要求或建议（可加标签如 #主线 #感情线 #伏笔）",
                placeholder="例如：主角性格要更果断 / 增加对战场的环境描写 / 参考真正的唐代官制来写朝廷...",
                lines=2,
            )

            write_all_btn.click(
                app.write_all_chapters,
                [writing_suggestions],
                [write_status, write_log],
            )

            gr.Markdown("---")
            gr.Markdown("### 单章写作 / 审阅 / 修改")

            with gr.Row():
                vol_input = gr.Number(label="卷号", value=1, precision=0, minimum=1)
                ch_input = gr.Number(label="章号", value=1, precision=0, minimum=1)

            with gr.Row():
                write_one_btn = gr.Button("✍️ 写此章")
                review_btn = gr.Button("🔍 审阅此章")
                revise_btn = gr.Button("✏️ 修改此章")

            chapter_content = gr.Textbox(
                label="正文",
                lines=20,
                interactive=False,
                autoscroll=True,
            )
            review_report = gr.Textbox(
                label="审阅报告",
                lines=8,
                interactive=True,
                placeholder="审阅后此处显示报告，可手动编辑后点击「修改此章」",
            )
            single_chapter_status = gr.Markdown("")

            write_one_btn.click(
                app.write_single_chapter,
                [vol_input, ch_input],
                [chapter_content, single_chapter_status, write_log],
            )
            review_btn.click(
                app.review_chapter,
                [vol_input, ch_input],
                [review_report],
            )
            revise_btn.click(
                app.revise_chapter,
                [vol_input, ch_input, review_report],
                [chapter_content, write_log],
            )

        # ═══════════════════════════════════════
        # Tab 5: Reading
        # ═══════════════════════════════════════
        with gr.Tab("📖 阅读"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 导航")
                    read_vol = gr.Number(label="卷", value=1, precision=0, minimum=1)
                    read_ch = gr.Number(label="章", value=1, precision=0, minimum=1)
                    read_btn = gr.Button("📖 读取", variant="primary")

                    # Quick nav: previous/next
                    with gr.Row():
                        prev_ch_btn = gr.Button("⬅ 上一章")
                        next_ch_btn = gr.Button("下一章 ➡")

                with gr.Column(scale=3):
                    read_title = gr.Markdown("### 正文")
                    read_content = gr.Textbox(
                        label="",
                        lines=25,
                        interactive=False,
                        autoscroll=True,
                        show_label=False,
                    )

            read_btn.click(
                app.get_chapter_content,
                [read_vol, read_ch],
                [read_content],
            )

            def prev_chapter(v, c):
                return v, max(1, c - 1)

            def next_chapter(v, c):
                if not app.project:
                    return v, c
                # Find next chapter
                for vol in app.project.volumes:
                    if vol.volume_number == v:
                        max_c = len(vol.chapters)
                        if c < max_c:
                            return v, c + 1
                        elif v < len(app.project.volumes):
                            return v + 1, 1
                return v, c

            prev_ch_btn.click(
                prev_chapter, [read_vol, read_ch], [read_vol, read_ch]
            ).then(
                app.get_chapter_content, [read_vol, read_ch], [read_content]
            )

            next_ch_btn.click(
                next_chapter, [read_vol, read_ch], [read_vol, read_ch]
            ).then(
                app.get_chapter_content, [read_vol, read_ch], [read_content]
            )

        # ═══════════════════════════════════════
        # Tab 6: Export
        # ═══════════════════════════════════════
        with gr.Tab("📥 导出"):
            gr.Markdown("### 多格式导出")

            with gr.Row():
                export_fmt = gr.Dropdown(
                    ["md", "txt", "epub", "pdf", "docx"],
                    label="格式",
                    value="epub",
                )
                export_btn = gr.Button("📥 导出", variant="primary")
                export_all_btn = gr.Button("📦 全部导出")

            export_path = gr.Textbox(label="文件路径", interactive=False)
            export_msg = gr.Markdown("")

            export_btn.click(
                app.export_format,
                [export_fmt],
                [export_path, export_msg],
            )
            export_all_btn.click(
                app.export_all_formats,
                [],
                [export_msg],
            )

            gr.Markdown("---")
            gr.Markdown("### 🔊 有声书导出")

            with gr.Row():
                audio_fmt = gr.Dropdown(
                    ["m4a", "mp3"],
                    label="音频格式",
                    value="m4a",
                    info="m4a(AAC) = 高质量小体积 | mp3 = 广泛兼容",
                )
                audio_voice = gr.Dropdown(
                    [
                        "zh-CN-XiaoxiaoNeural (晓晓-温柔女声)",
                        "zh-CN-YunxiNeural (云希-阳光男声)",
                        "zh-CN-XiaoyiNeural (晓伊-活泼女声)",
                        "zh-CN-YunyangNeural (云扬-专业旁白)",
                        "zh-CN-XiaohanNeural (晓涵-自然女声)",
                        "zh-CN-YunjianNeural (云健-磁性男声)",
                    ],
                    label="朗读者声优",
                    value="zh-CN-XiaoxiaoNeural (晓晓-温柔女声)",
                )
                audio_split = gr.Checkbox(label="每章独立文件", value=True,
                                           info="勾选=每章一个文件，不勾选=整本合并")
                audio_export_btn = gr.Button("🔊 生成有声书", variant="secondary")

            audio_status = gr.Markdown("")
            audio_log = gr.Textbox(label="🎤 生成日志", lines=4, interactive=False)

            def export_audio_web(fmt, voice, per_chapter):
                """WebUI 音频导出。"""
                if not app.project:
                    return "❌ 请先创建或加载项目", "无项目"
                import io
                import sys
                from contextlib import redirect_stdout

                buf = io.StringIO()
                with redirect_stdout(buf):
                    try:
                        exp = Exporter(app.project)
                        voice_name = voice.split(" ")[0] if " " in voice else voice
                        path = exp.export_audio(fmt=fmt, per_chapter=per_chapter, voice=voice_name)
                        app.log(f"🔊 有声书导出: {fmt} | {voice_name}")
                        status = f"✅ 有声书已生成: {path}"
                    except ImportError as e:
                        if 'edge_tts' in str(e):
                            status = "❌ 需要安装 edge-tts: pip install edge-tts"
                        else:
                            status = f"❌ 导出失败: {e}"
                        app.log(status)
                    except Exception as e:
                        status = f"❌ {e}"
                        app.log(status)
                return status, buf.getvalue()

            audio_export_btn.click(
                export_audio_web,
                [audio_fmt, audio_voice, audio_split],
                [audio_status, audio_log],
            )

            gr.Markdown("---")
            gr.Markdown("### 下载文件")
            gr.Markdown("导出后，文件保存在桌面的 `DeepSeekWriter/<书名>/` 目录下。")
            gr.Markdown("""
            支持格式:
            - **MD**: Markdown，可导入大多数写作工具
            - **TXT**: 纯文本，通用格式
            - **EPUB**: 电子书，支持 Kindle / Apple Books / 微信读书
            - **PDF**: 适合打印或分享
            - **DOCX**: Word 文档，可进一步编辑
            - **m4a/mp3**: 有声书，使用 Microsoft Edge 免费 TTS
            """)

        # ═══════════════════════════════════════
        # Tab 7: Projects
        # ═══════════════════════════════════════
        with gr.Tab("📂 项目管理"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 已保存项目")
                    refresh_list_btn = gr.Button("🔄 刷新列表")
                    project_list = gr.Markdown(app.list_saved())

                with gr.Column(scale=1):
                    gr.Markdown("### 操作")
                    load_name = gr.Textbox(label="项目名称")
                    with gr.Row():
                        load_btn = gr.Button("📂 加载", variant="primary")
                        delete_btn = gr.Button("🗑 删除", variant="stop")
                    project_op_result = gr.Markdown("")

            refresh_list_btn.click(app.list_saved, [], [project_list])
            load_btn.click(app.load_project, [load_name], [project_op_result, log_box])
            delete_btn.click(app.delete_project, [load_name], [project_op_result])

        # ═══════════════════════════════════════
        # Tab 8: Statistics
        # ═══════════════════════════════════════
        with gr.Tab("📊 统计"):
            stats_refresh_btn = gr.Button("🔄 刷新")
            stats_md = gr.Markdown(app.get_stats())
            stats_refresh_btn.click(app.get_stats, [], [stats_md])

        # ── Footer ──
        gr.Markdown("---\n*DeepSeek Writer — AI-Assisted Novel Writing Tool*")

    # Launch
    ui.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True,
        inbrowser=True,
    )


if __name__ == "__main__":
    build_ui()
