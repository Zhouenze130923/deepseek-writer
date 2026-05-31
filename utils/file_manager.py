from __future__ import annotations
import json
import os
import shutil
from pathlib import Path
from project import Project


class FileManager:
    """
    项目管理器。项目存储路径可通过环境变量 DEEPSEEK_WRITER_DIR 自定义。
    默认: ~/Desktop/DeepSeekWriter/
    """

    def __init__(self, base_path: str | Path | None = None):
        self.base_path = Path(base_path) if base_path else Path(
            os.environ.get("DEEPSEEK_WRITER_DIR") or Path.home() / "Desktop" / "DeepSeekWriter"
        )
        self.base_path.mkdir(parents=True, exist_ok=True)

    def project_dir(self, title: str) -> Path:
        safe = "".join(c for c in title if c.isalnum() or c in " _-").strip() or "Untitled"
        return self.base_path / safe

    def save(self, project: Project):
        proj_dir = self.project_dir(project.title)
        proj_dir.mkdir(parents=True, exist_ok=True)
        import datetime
        project.updated_at = datetime.datetime.now().isoformat()
        (proj_dir / "project.json").write_text(json.dumps(project.to_dict(), ensure_ascii=False, indent=2))
        self._export_outline(project, proj_dir)
        self._export_characters(project, proj_dir)
        self._export_chapters(project, proj_dir)
        return proj_dir

    def load(self, project_name: str) -> Project | None:
        proj_dir = self.project_dir(project_name)
        project_file = proj_dir / "project.json"
        if not project_file.exists():
            return None
        return Project.from_dict(json.loads(project_file.read_text()))

    def list_projects(self) -> list[str]:
        if not self.base_path.exists():
            return []
        return [d.name for d in self.base_path.iterdir() if d.is_dir() and (d / "project.json").exists()]

    def delete_project(self, title: str):
        proj_dir = self.project_dir(title)
        if proj_dir.exists():
            shutil.rmtree(proj_dir)

    def _export_outline(self, project, proj_dir):
        lines = [f"# {project.title} - 大纲", "", f"- 类型: {project.genre}", f"- 梗概: {project.premise}", f"- 主题: {project.theme}", f"- 基调: {project.tone}", ""]
        for vol in project.volumes:
            lines.append(f"## 第{vol.volume_number}卷「{vol.volume_title}」")
            lines.append(f"_{vol.synopsis}_\n")
            for ch in vol.chapters:
                lines.append(f"### 第{ch.chapter_number}章「{ch.chapter_title}」")
                lines.append(f"{ch.synopsis}\n")
        (proj_dir / "大纲.md").write_text("\n".join(lines))

    def _export_characters(self, project, proj_dir):
        chars = project.characters
        lines = ["# 人物档案", ""]
        for c in chars.get("characters", []):
            lines.append(f"## {c['name']}（{c.get('role','')}）")
            lines.append(f"- 年龄: {c.get('age','')} | 外貌: {c.get('appearance','')}")
            lines.append(f"- 性格: {c.get('personality','')}")
            lines.append(f"- 背景: {c.get('background','')}")
            lines.append(f"- 动机: {c.get('motivation','')}")
            lines.append(f"- 弧线: {c.get('arc','')}")
            lines.append("")
        ws = project.writing_style
        if ws:
            lines.append("# 写作风格")
            for key, val in ws.items():
                lines.append(f"- {key}: {val if isinstance(val, str) else ', '.join(val)}")
            lines.append("")
        (proj_dir / "人物档案.md").write_text("\n".join(lines))

    def _export_chapters(self, project, proj_dir):
        for vol in project.volumes:
            vol_dir = proj_dir / f"第{vol.volume_number}卷"
            vol_dir.mkdir(parents=True, exist_ok=True)
            for ch in vol.chapters:
                if ch.content:
                    (vol_dir / f"第{ch.chapter_number}章.md").write_text(f"# 第{ch.chapter_number}章「{ch.chapter_title}」\n\n{ch.content}")
