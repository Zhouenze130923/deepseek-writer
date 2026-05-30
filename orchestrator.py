from __future__ import annotations
from typing import Callable
from config import Config
from llm.client import LLMClient
from agents.outline import OutlineAgent
from agents.character import CharacterAgent
from agents.condenser import CondenserAgent
from agents.writer import WriterAgent
from agents.editor import EditorAgent
from project import Project


class Orchestrator:
    MAX_PARALLEL_WRITERS = 5

    def __init__(self, config: Config):
        self.config = config
        self.client = LLMClient(config)
        self.outline_agent = OutlineAgent(self.client, config)
        self.character_agent = CharacterAgent(self.client, config)
        self.condenser_agent = CondenserAgent()
        self.editor_agent = EditorAgent(self.client, config)
        self.writer_agents: list[WriterAgent] = []

    def _get_writer(self) -> WriterAgent:
        if not self.writer_agents:
            self.writer_agents.append(WriterAgent(self.client, self.config))
        return self.writer_agents[0]

    def generate_outline(self, premise: str, template_guide: str = "") -> dict:
        return self.outline_agent.generate(premise=premise, template_guide=template_guide)

    def design_characters(self, outline: dict, style: str = "自动匹配") -> dict:
        return self.character_agent.design(outline=outline, style=style)

    def condense(self, outline: dict, characters: dict, writing_style: dict) -> dict:
        return self.condenser_agent.condense(outline=outline, characters=characters, writing_style=writing_style)

    def get_foreshadowing_context(self, project: Project, volume_number: int, chapter_number: int) -> tuple[str, str]:
        unresolved = project.foreshadowing.to_context(volume_number, chapter_number)
        return "", unresolved

    def get_bible_context(self, project: Project, volume_number: int, chapter_number: int) -> str:
        return project.bible.to_context(volume_number, chapter_number)

    def review_chapter(self, project: Project, volume_idx: int, chapter_idx: int, *,
                       on_chunk: Callable[[str], None] | None = None) -> str:
        volume = project.volumes[volume_idx]
        chapter = volume.chapters[chapter_idx]
        bible_ctx = self.get_bible_context(project, volume.volume_number, chapter.chapter_number)

        if on_chunk:
            report = ""
            for chunk in self.editor_agent.review_stream(
                title=project.title, genre=project.genre,
                volume_number=volume.volume_number, volume_title=volume.volume_title,
                chapter_number=chapter.chapter_number, chapter_title=chapter.chapter_title,
                content=chapter.content, characters=project.characters,
                writing_style=project.writing_style, bible_context=bible_ctx,
            ):
                report += chunk; on_chunk(chunk)
            return report
        return self.editor_agent.review(
            title=project.title, genre=project.genre,
            volume_number=volume.volume_number, volume_title=volume.volume_title,
            chapter_number=chapter.chapter_number, chapter_title=chapter.chapter_title,
            content=chapter.content, characters=project.characters,
            writing_style=project.writing_style, bible_context=bible_ctx,
        )
