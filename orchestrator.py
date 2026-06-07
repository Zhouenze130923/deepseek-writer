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
from utils.search import get_search_engine, SearchEngine


# 搜索关键词提取
_SEARCH_KEYWORDS = {
    "历史": ["历史", "时代背景", "古代", "朝代", "战役", "皇帝", "帝王"],
    "文化": ["文化", "民俗", "节日", "宗教", "神话", "传说", "礼仪"],
    "地理": ["地理", "地域", "国家", "城市", "气候", "地貌"],
    "科技": ["科技", "技术", "科学", "发明", "医学", "天文"],
    "职业": ["职业", "身份", "工作", "行业", "技能"],
}


class Orchestrator:
    MAX_PARALLEL_WRITERS = 5

    def __init__(self, config: Config):
        self.config = config
        self.client = LLMClient(config)
        self.outline_agent = OutlineAgent(self.client, config)
        self.character_agent = CharacterAgent(self.client, config)
        self.condenser_agent = CondenserAgent(self.client, config)
        self.editor_agent = EditorAgent(self.client, config)
        self.writer_agents: list[WriterAgent] = []

    def _get_writer(self, volume_idx: int = 0) -> WriterAgent:
        """获取写作子代理。不同卷可以用不同子代理，确保独立写作风格。"""
        while len(self.writer_agents) <= volume_idx:
            self.writer_agents.append(WriterAgent(self.client, self.config))
        return self.writer_agents[volume_idx]

    def _do_search(self, query: str) -> str:
        """执行联网搜索，返回格式化上下文。搜索失败时返回空字符串。"""
        if not self.config.search_enabled:
            return ""
        try:
            engine = get_search_engine({
                "search_provider": self.config.search_provider,
                "tavily_api_key": self.config.tavily_api_key,
                "searxng_base_url": self.config.searxng_base_url,
            })
            results = engine.search(query, max_results=5)
            return engine.format_context(results)
        except Exception as e:
            return f"\n## 联网搜索备注\n搜索失败: {e}\n"

    def _extract_search_queries(self, text: str) -> list[str]:
        """从文本中提取搜索关键词。"""
        queries = []
        for category, keywords in _SEARCH_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    queries.append(f"{text[:60]} {kw}")
                    break
        return queries[:2]

    def generate_outline(self, premise: str, template_guide: str = "",
                         user_suggestions: str = "") -> dict:
        """生成大纲。如果启用了搜索，自动搜索相关背景信息。"""
        search_context = self._do_search(premise)
        return self.outline_agent.generate(
            premise=premise,
            template_guide=template_guide,
            search_context=search_context,
            user_suggestions=user_suggestions,
        )

    def design_characters(self, outline: dict, style: str = "自动匹配", constraints: str = "") -> dict:
        return self.character_agent.design(outline=outline, style=style, character_requirements=constraints)

    def condense(self, outline: dict, characters: dict, writing_style: dict) -> dict:
        return self.condenser_agent.condense(outline=outline, characters=characters, writing_style=writing_style)

    def get_foreshadowing_context(self, project: Project, volume_number: int, chapter_number: int) -> tuple[str, str]:
        unresolved = project.foreshadowing.to_context(volume_number, chapter_number)
        return "", unresolved

    def get_bible_context(self, project: Project, volume_number: int, chapter_number: int) -> str:
        return project.bible.to_context(volume_number, chapter_number)

    def write_single_chapter(self, project: Project, volume_idx: int, chapter_idx: int,
                              brief: dict, review_rounds: int = 1, parallel_editors: bool = False,
                              on_chunk=None, on_review=None,
                              parallel_writers: bool = False, num_scenes: int = 3) -> str:
        """写入并审阅单个章节。
        如果 parallel_writers=True，使用多个子代理并行写不同场景后合并。
        """
        volume = project.volumes[volume_idx]
        chapter = volume.chapters[chapter_idx]

        prev_ctx = project.get_chapter_context(volume_idx, chapter_idx)
        bible_ctx = self.get_bible_context(project, volume.volume_number, chapter.chapter_number)
        _, unresolved = self.get_foreshadowing_context(project, volume.volume_number, chapter.chapter_number)

        writer = self._get_writer()

        if parallel_writers and num_scenes > 1:
            content = writer.write_parallel(
                brief=brief, volume_number=volume.volume_number,
                volume_title=volume.volume_title, volume_goal=volume.synopsis,
                chapter_number=chapter.chapter_number, chapter_title=chapter.chapter_title,
                must_happen=chapter.synopsis, pov=chapter.pov_character,
                previous_context=prev_ctx, bible_context=bible_ctx,
                num_scenes=num_scenes,
            )
        else:
            content = writer.write_chapter(
                brief=brief, volume_number=volume.volume_number,
                volume_title=volume.volume_title, volume_goal=volume.synopsis,
                chapter_number=chapter.chapter_number, chapter_title=chapter.chapter_title,
                must_happen=chapter.synopsis, pov=chapter.pov_character,
                previous_context=prev_ctx, plant_foreshadowing="",
                resolve_foreshadowing=unresolved, bible_context=bible_ctx,
            )
        chapter.content = content

        for round_idx in range(review_rounds):
            report = self.review_chapter(
                project, volume_idx, chapter_idx, brief,
                parallel=parallel_editors, on_chunk=on_review,
            )
            if report and round_idx < review_rounds - 1:
                content = writer.revise_chapter(
                    brief=brief, original_content=content, editor_report=report,
                )
                chapter.content = content

        chapter.status = "done"
        return content

    def get_editor_strictness(self) -> dict:
        """返回编辑器严格度配置，供外部逻辑使用。"""
        return self.editor_agent.get_strictness_config()

    def review_chapter(self, project: Project, volume_idx: int, chapter_idx: int,
                       brief: dict, *, parallel: bool = False,
                       on_chunk: Callable[[str], None] | None = None) -> str:
        volume = project.volumes[volume_idx]
        chapter = volume.chapters[chapter_idx]
        bible_ctx = self.get_bible_context(project, volume.volume_number, chapter.chapter_number)

        if parallel:
            return self.editor_agent.review_parallel(
                title=project.title, genre=project.genre,
                volume_number=volume.volume_number, volume_title=volume.volume_title,
                chapter_number=chapter.chapter_number, chapter_title=chapter.chapter_title,
                content=chapter.content, brief=brief, bible_context=bible_ctx,
            )

        if on_chunk:
            report = ""
            for chunk in self.editor_agent.review_stream(
                title=project.title, genre=project.genre,
                volume_number=volume.volume_number, volume_title=volume.volume_title,
                chapter_number=chapter.chapter_number, chapter_title=chapter.chapter_title,
                content=chapter.content, brief=brief, bible_context=bible_ctx,
            ):
                report += chunk; on_chunk(chunk)
            return report
        return self.editor_agent.review(
            title=project.title, genre=project.genre,
            volume_number=volume.volume_number, volume_title=volume.volume_title,
            chapter_number=chapter.chapter_number, chapter_title=chapter.chapter_title,
            content=chapter.content, brief=brief, bible_context=bible_ctx,
        )
