from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from utils.foreshadowing import ForeshadowTracker
from utils.continuity import ContinuityBible


@dataclass
class Chapter:
    chapter_number: int
    chapter_title: str
    synopsis: str
    key_events: list[str] = field(default_factory=list)
    pov_character: str = ""
    word_count_target: int = 3000
    content: str = ""
    status: str = "pending"


@dataclass
class Volume:
    volume_number: int
    volume_title: str
    synopsis: str
    chapters: list[Chapter] = field(default_factory=list)
    status: str = "pending"


@dataclass
class Project:
    title: str = ""
    genre: str = ""
    premise: str = ""
    theme: str = ""
    tone: str = ""
    volumes: list[Volume] = field(default_factory=list)
    characters: dict = field(default_factory=dict)
    plot_arcs: dict = field(default_factory=dict)
    world_building: dict = field(default_factory=dict)
    writing_style: dict = field(default_factory=dict)
    style_reference: dict = field(default_factory=dict)
    target_audience: str = ""
    template: str = ""
    created_at: str = ""
    updated_at: str = ""
    current_stage: str = "new"
    foreshadowing: ForeshadowTracker = field(default_factory=ForeshadowTracker)
    bible: ContinuityBible = field(default_factory=ContinuityBible)

    def __post_init__(self):
        if not self.created_at: self.created_at = datetime.now().isoformat()
        if not self.updated_at: self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        # ForeshadowTracker 和 ContinuityBible 不是纯 dataclass，替换为自定义序列化
        d["foreshadowing"] = self.foreshadowing.to_dict()
        d["bible"] = self.bible.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        project = cls(
            title=data.get("title", ""), genre=data.get("genre", ""),
            premise=data.get("premise", ""), theme=data.get("theme", ""),
            tone=data.get("tone", ""), characters=data.get("characters", {}),
            plot_arcs=data.get("plot_arcs", {}), world_building=data.get("world_building", {}),
            writing_style=data.get("writing_style", {}), style_reference=data.get("style_reference", {}),
            target_audience=data.get("target_audience", ""), template=data.get("template", ""),
            created_at=data.get("created_at", ""), updated_at=data.get("updated_at", ""),
            current_stage=data.get("current_stage", "new"),
        )
        for v_data in data.get("volumes", []):
            volume = Volume(volume_number=v_data["volume_number"], volume_title=v_data["volume_title"],
                            synopsis=v_data["synopsis"], status=v_data.get("status", "pending"))
            for c_data in v_data.get("chapters", []):
                chapter = Chapter(chapter_number=c_data["chapter_number"], chapter_title=c_data["chapter_title"],
                                  synopsis=c_data["synopsis"], key_events=c_data.get("key_events", []),
                                  pov_character=c_data.get("pov_character", ""),
                                  word_count_target=c_data.get("word_count_target", 3000),
                                  content=c_data.get("content", ""), status=c_data.get("status", "pending"))
                volume.chapters.append(chapter)
            project.volumes.append(volume)
        if data.get("foreshadowing"): project.foreshadowing = ForeshadowTracker.from_dict(data["foreshadowing"])
        if data.get("bible"): project.bible = ContinuityBible.from_dict(data["bible"])
        return project

    def get_next_pending_chapter(self) -> tuple[int, int, Chapter] | None:
        for vi, volume in enumerate(self.volumes):
            for ci, chapter in enumerate(volume.chapters):
                if chapter.status == "pending": return vi, ci, chapter
        return None

    def get_chapter_context(self, volume_idx: int, chapter_idx: int) -> str:
        parts = []
        for vi in range(volume_idx + 1):
            volume = self.volumes[vi]
            for ci, chapter in enumerate(volume.chapters):
                if vi == volume_idx and ci >= chapter_idx: break
                if chapter.status == "done" and chapter.content:
                    parts.append(f"V{volume.volume_number}C{chapter.chapter_number}「{chapter.chapter_title}」: {chapter.synopsis}")
        return "\n".join(parts[-5:]) if parts else "无"
