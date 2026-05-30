from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Foreshadow:
    id: str
    description: str
    planted_volume: int
    planted_chapter: int
    planted_text: str = ""
    target_volume: int = 0
    target_chapter: int = 0
    resolved_volume: int = 0
    resolved_chapter: int = 0
    resolved_text: str = ""
    thread: str = ""
    importance: str = "medium"
    status: str = "planted"


class ForeshadowTracker:
    def __init__(self):
        self.foreshadows: list[Foreshadow] = []
        self._counter = 0

    def plant(self, description: str, volume: int, chapter: int, thread: str = "", importance: str = "medium",
              target_volume: int = 0, target_chapter: int = 0) -> Foreshadow:
        self._counter += 1
        f = Foreshadow(id=f"v{volume}c{chapter}-{self._counter}", description=description,
                       planted_volume=volume, planted_chapter=chapter, thread=thread,
                       importance=importance, target_volume=target_volume, target_chapter=target_chapter)
        self.foreshadows.append(f)
        return f

    def resolve(self, f_id: str, volume: int, chapter: int) -> Foreshadow | None:
        for f in self.foreshadows:
            if f.id == f_id:
                f.resolved_volume = volume; f.resolved_chapter = chapter; f.status = "resolved"
                return f
        return None

    def get_unresolved(self, before_volume: int | None = None) -> list[Foreshadow]:
        unresolved = [f for f in self.foreshadows if f.status == "planted"]
        if before_volume is not None:
            unresolved = [f for f in unresolved if f.planted_volume < before_volume]
        return unresolved

    def stats(self) -> dict:
        total = len(self.foreshadows)
        resolved = sum(1 for f in self.foreshadows if f.status == "resolved")
        critical = sum(1 for f in self.foreshadows if f.status == "planted" and f.importance == "critical")
        return {"total": total, "resolved": resolved, "unresolved": total - resolved,
                "critical_unresolved": critical, "rate": f"{resolved/total*100:.0f}%" if total > 0 else "N/A"}

    def to_context(self, for_volume: int, for_chapter: int) -> str:
        def before(f):
            return f.planted_volume < for_volume or (f.planted_volume == for_volume and f.planted_chapter < for_chapter)
        unresolved = [f for f in self.get_unresolved() if before(f)]
        if not unresolved:
            return ""
        lines = ["## 待回收伏笔"]
        urgent = [f for f in unresolved if f.importance in ("high", "critical")]
        normal = [f for f in unresolved if f.importance not in ("high", "critical")]
        if urgent:
            lines.append("\n### 关键伏笔")
            for f in urgent:
                lines.append(f"- [{f.id}] {f.description} (埋于V{f.planted_volume}C{f.planted_chapter})")
        if normal:
            lines.append("\n### 普通伏笔")
            for f in normal[-10:]:
                lines.append(f"- [{f.id}] {f.description} (埋于V{f.planted_volume}C{f.planted_chapter})")
        return "\n".join(lines)

    def to_dict(self) -> list[dict]:
        return [{"id": f.id, "description": f.description, "planted_volume": f.planted_volume,
                 "planted_chapter": f.planted_chapter, "target_volume": f.target_volume,
                 "target_chapter": f.target_chapter, "resolved_volume": f.resolved_volume,
                 "resolved_chapter": f.resolved_chapter, "thread": f.thread,
                 "importance": f.importance, "status": f.status} for f in self.foreshadows]

    @classmethod
    def from_dict(cls, data: list[dict]) -> "ForeshadowTracker":
        tracker = cls()
        for d in data:
            tracker.foreshadows.append(Foreshadow(id=d["id"], description=d["description"],
                planted_volume=d["planted_volume"], planted_chapter=d["planted_chapter"],
                target_volume=d.get("target_volume", 0), target_chapter=d.get("target_chapter", 0),
                resolved_volume=d.get("resolved_volume", 0), resolved_chapter=d.get("resolved_chapter", 0),
                thread=d.get("thread", ""), importance=d.get("importance", "medium"),
                status=d.get("status", "planted")))
            tracker._counter = len(data)
        return tracker
