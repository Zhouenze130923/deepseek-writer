from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Fact:
    category: str
    key: str
    value: str
    established_volume: int
    established_chapter: int
    source: str = ""


class ContinuityBible:
    CATEGORIES = ["character", "plot", "world", "timeline", "item", "relationship"]

    def __init__(self):
        self.facts: list[Fact] = []
        self._context_cache: dict[tuple, str] = {}
        self._facts_version = 0

    def _invalidate_cache(self):
        self._context_cache.clear()
        self._facts_version += 1

    def establish(self, category: str, key: str, value: str, volume: int, chapter: int, source: str = "") -> Fact:
        for f in self.facts:
            if f.category == category and f.key == key:
                if f.value != value:
                    f.value = value; f.established_volume = volume; f.established_chapter = chapter; f.source = source
                    self._invalidate_cache()
                return f
        fact = Fact(category=category, key=key, value=value, established_volume=volume, established_chapter=chapter, source=source)
        self.facts.append(fact)
        self._invalidate_cache()
        return fact

    def get_category(self, category: str) -> list[Fact]:
        return [f for f in self.facts if f.category == category]

    def to_context(self, for_volume: int, for_chapter: int) -> str:
        cache_key = (for_volume, for_chapter, self._facts_version)
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]

        def before(f):
            if f.established_volume < for_volume: return True
            if f.established_volume == for_volume and f.established_chapter < for_chapter: return True
            return f.established_volume == 0
        chars = [f for f in self.get_category("character") if before(f)]
        world = [f for f in self.get_category("world") if before(f)]
        items = [f for f in self.get_category("item") if before(f)]
        lines = ["## 世界圣经"]
        if chars:
            lines.append("\n### 人物事实")
            for f in chars[-30:]:
                lines.append(f"- {f.key}: {f.value} (V{f.established_volume}C{f.established_chapter})")
        if world:
            lines.append("\n### 世界观规则")
            for f in world[-15:]:
                lines.append(f"- {f.key}: {f.value}")
        if items:
            lines.append("\n### 关键物品")
            for f in items[-10:]:
                lines.append(f"- {f.key}: {f.value}")
        result = "\n".join(lines)
        self._context_cache[cache_key] = result
        return result

    def stats(self) -> dict:
        by_cat = {c: len(self.get_category(c)) for c in self.CATEGORIES}
        return {"total": len(self.facts), **by_cat}

    def to_dict(self) -> list[dict]:
        return [{"category": f.category, "key": f.key, "value": f.value,
                 "established_volume": f.established_volume, "established_chapter": f.established_chapter,
                 "source": f.source} for f in self.facts]

    @classmethod
    def from_dict(cls, data: list[dict]) -> "ContinuityBible":
        bible = cls()
        for d in data:
            bible.facts.append(Fact(category=d["category"], key=d["key"], value=d["value"],
                established_volume=d["established_volume"], established_chapter=d["established_chapter"],
                source=d.get("source", "")))
        return bible
