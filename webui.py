#!/usr/bin/env python3
"""DeepSeek Writer - Web 界面 (Gradio)。"""

from __future__ import annotations
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from orchestrator import Orchestrator
from project import Project, Volume, Chapter
from utils.file_manager import FileManager
from utils.exporter import Exporter
from utils.memory import MemoryStore
from templates import list_templates, get_template, template_to_prompt


class WebApp:
    def __init__(self):
        self.config = Config.load()
        self.orchestrator = Orchestrator(self.config)
        self.file_manager = FileManager()
        self.project: Project | None = None
        self.brief: dict | None = None
        self.memory: MemoryStore | None = None
        self.logs: list[str] = []

    def log(self, msg: str):
        self.logs.append(msg)
        return "\n".join(self.logs[-30:])

    def clear_logs(self):
        self.logs = []
        return ""

    def set_api(self, provider, api_key, model):
        self.config.provider = provider
        if provider == "deepseek":
            self.config.deepseek_api_key = api_key
            self.config.model = model
        else:
            self.config.claude_api_key = api_key
            self.config.claude_model = model
        self.config.save()
        self.orchestrator = Orchestrator(self.config)
        return f"已配置: {provider} - {model}"

    def new_project(self, idea, template_name):
        self.project = Project(premise=idea)
        self.brief = None
        self.memory = MemoryStore("")
        template = None
        if template_name and template_name != "自动":
            tmpl = get_template(template_name)
            if tmpl:
                template = {"name": template_name, **tmpl}

        self.log(f"创建项目: {idea[:50]}...")
        template_guide = template_to_prompt(template) if template else ""

        outline = self.orchestrator.generate_outline(premise=idea, template_guide=template_guide)
        self._load_outline(outline)
        self.log(f"大纲: {self.project.title} ({self.project.genre}) {len(self.project.volumes)}卷")

        chars = self.orchestrator.design_characters(outline=self.project.to_dict(), style="自动匹配")
        self._load_characters(chars)
        self.log(f"人物: {len(chars.get('characters',[]))} 个")

        self.brief = self.orchestrator.condense(
            outline=self.project.to_dict(),
            characters=self.project.characters,
            writing_style=self.project.writing_style,
        )
        self.log("凝练完成，可以开始写作")

        return self._status_text()

    def write_all(self):
        if not self.project or not self.brief:
            return "请先创建项目"
        total = sum(len(v.chapters) for v in self.project.volumes)
        self.log(f"开始写作 {len(self.project.volumes)}卷 {total}章...")

        for vi, volume in enumerate(self.project.volumes):
            vol_plan = self.brief.get("volume_plan", [])
            vol_brief = vol_plan[vi] if vi < len(vol_plan) else {}
            volume_goal = vol_brief.get("goal", volume.synopsis)

            for ci, chapter in enumerate(volume.chapters):
                if chapter.status == "done":
                    continue
                ch_brief = vol_brief.get("chapters", [])
                ch_plan = ch_brief[ci] if ci < len(ch_brief) else {}
                must_happen = ch_plan.get("must_happen", chapter.synopsis)
                pov = ch_plan.get("pov", chapter.pov_character)
                prev = self._prev_context(vi, ci)

                mem_ctx = ""
                if self.memory:
                    mem_ctx = self.memory.get_context_for_chapter(
                        volume.volume_number, chapter.chapter_number, must_happen
                    )

                writer = self.orchestrator._get_writer()
                _, resolve_fs = self.orchestrator.get_foreshadowing_context(
                    self.project, volume.volume_number, chapter.chapter_number
                )
                bible_ctx = self.orchestrator.get_bible_context(
                    self.project, volume.volume_number, chapter.chapter_number
                )

                content = writer.write_chapter(
                    brief=self.brief,
                    volume_number=volume.volume_number, volume_title=volume.volume_title,
                    volume_goal=volume_goal, chapter_number=chapter.chapter_number,
                    chapter_title=chapter.chapter_title, must_happen=must_happen, pov=pov,
                    previous_context=prev,
                    plant_foreshadowing="自然植入大纲中的伏笔",
                    resolve_foreshadowing=resolve_fs,
                    bible_context=bible_ctx + "\n" + mem_ctx,
                )
                chapter.content = content
                chapter.status = "done"

                if self.memory:
                    self.memory.add_chapter_summary(
                        volume.volume_number, chapter.chapter_number,
                        chapter.synopsis, pov, ", ".join(chapter.key_events[:3])
                    )

                self.log(f"V{volume.volume_number}C{chapter.chapter_number}「{chapter.chapter_title}」({len(content)}字)")

            volume.status = "done"

        self.project.current_stage = "done"
        self.file_manager.save(self.project)
        self.log("写作完成!")
        return self._status_text()

    def export_files(self, fmt):
        if not self.project:
            return "请先创建项目"
        exp = Exporter(self.project)
        results = {"md": exp.export_markdown, "txt": exp.export_txt,
                   "epub": exp.export_epub, "pdf": exp.export_pdf,
                   "docx": exp.export_docx}
        if fmt in results:
            path = results[fmt]()
            return f"导出: {path}"
        return "不支持的格式"

    def load_project(self, name):
        proj = self.file_manager.load(name)
        if proj:
            self.project = proj
            return self._status_text()
        return f"未找到: {name}"

    def list_saved(self):
        return "\n".join(self.file_manager.list_projects()) or "(无)"

    def get_content(self, volume, chapter):
        if not self.project:
            return ""
        for v in self.project.volumes:
            if v.volume_number == volume:
                for c in v.chapters:
                    if c.chapter_number == chapter:
                        return c.content or "(未写)"
        return "(未找到)"

    def _load_outline(self, outline):
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

    def _load_characters(self, chars):
        self.project.characters = chars
        self.project.writing_style = chars.get("writing_style", {})
        for c in chars.get("characters", []):
            self.project.bible.establish("character", f"{c['name']}.role", c.get("role", ""), 0, 0)

    def _prev_context(self, vi, ci):
        if ci == 0:
            return ""
        prev = self.project.volumes[vi].chapters[ci - 1]
        if prev.content:
            return f"上一章结尾: ...{prev.content[-300:]}"
        return f"前一章「{prev.chapter_title}」: {prev.synopsis}"

    def _status_text(self):
        if not self.project:
            return "无项目"
        vols = len(self.project.volumes)
        total_ch = sum(len(v.chapters) for v in self.project.volumes)
        done_ch = sum(1 for v in self.project.volumes for c in v.chapters if c.status == "done")
        total_words = sum(len(c.content) for v in self.project.volumes for c in v.chapters)
        return f"""## 《{self.project.title}》
- 类型: {self.project.genre} | {vols}卷 {total_ch}章
- 进度: {done_ch}/{total_ch} 章 | 约{total_words}字
- 梗概: {self.project.premise}"""


def build_ui():
    try:
        import gradio as gr
    except ImportError:
        print("需要安装: pip install gradio")
        return

    app = WebApp()

    with gr.Blocks(title="DeepSeek Writer") as ui:
        gr.Markdown("# DeepSeek Writer - AI 写作助手")

        with gr.Tab("配置"):
            provider = gr.Dropdown(["deepseek", "claude"], label="提供商", value=app.config.provider)
            api_key = gr.Textbox(label="API Key", type="password")
            model = gr.Textbox(label="模型", value=app.config.model)
            config_btn = gr.Button("保存配置")
            config_result = gr.Textbox(label="结果")
            config_btn.click(app.set_api, [provider, api_key, model], [config_result])

        with gr.Tab("创作"):
            idea = gr.Textbox(label="小说创意", placeholder="一个废柴少年获得修仙系统...")
            tmpl = gr.Dropdown(["自动"] + list_templates(), label="模版", value="自动")
            create_btn = gr.Button("1. 生成大纲+人物")
            write_btn = gr.Button("2. 开始写作")
            status = gr.Markdown("")
            logs = gr.Textbox(label="日志", lines=8, interactive=False)
            create_btn.click(app.new_project, [idea, tmpl], [status]).then(lambda: app.logs[-5:], None, [logs])
            write_btn.click(app.write_all, [], [status]).then(lambda: "\n".join(app.logs[-10:]), None, [logs])

        with gr.Tab("阅读"):
            v_num = gr.Number(label="卷", value=1, precision=0)
            c_num = gr.Number(label="章", value=1, precision=0)
            read_btn = gr.Button("读取")
            content = gr.Textbox(label="正文", lines=20, interactive=False)
            read_btn.click(app.get_content, [v_num, c_num], [content])

        with gr.Tab("导出"):
            fmt = gr.Dropdown(["md", "txt", "epub", "pdf", "docx"], label="格式", value="md")
            export_btn = gr.Button("导出")
            export_result = gr.Textbox(label="结果")
            export_btn.click(app.export_files, [fmt], [export_result])

        with gr.Tab("项目"):
            load_list = gr.Textbox(label="已保存项目", value=app.list_saved(), interactive=False)
            load_name = gr.Textbox(label="项目名")
            load_btn = gr.Button("加载")
            load_btn.click(app.load_project, [load_name], [status])

    ui.launch(share=False)


if __name__ == "__main__":
    build_ui()
