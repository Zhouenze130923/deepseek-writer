"""向量记忆系统——用 Chroma 存储和检索世界设定、关键事件、伏笔。

随着章节增多，自动检索相关记忆以保持上下文连贯。
"""

from __future__ import annotations


class MemoryStore:
    """轻量级记忆存储。使用内存模式（文本匹配检索），避免 chroma ONNX 模型下载卡死。"""

    def __init__(self, project_name: str = ""):
        self.project_name = project_name
        self._fallback: list[dict] = []

    def add(self, text: str, metadata: dict | None = None, doc_id: str = ""):
        """存储一条记忆。"""
        meta = metadata or {}
        self._fallback.append({"text": text, "meta": meta})

    def add_chapter_summary(self, volume: int, chapter: int, summary: str, characters: str, events: str):
        """存储章节摘要用于后续检索。"""
        combined = f"[V{volume}C{chapter}] 摘要: {summary} | 角色: {characters} | 事件: {events}"
        self.add(combined, {"type": "chapter", "volume": volume, "chapter": chapter}, f"v{volume}c{chapter}")

    def add_character_fact(self, name: str, fact: str):
        self.add(f"{name}: {fact}", {"type": "character", "name": name})

    def add_world_rule(self, rule: str):
        self.add(rule, {"type": "world_rule"})

    def add_foreshadow(self, description: str, volume: int, chapter: int):
        self.add(f"[V{volume}C{chapter}] 伏笔: {description}", {"type": "foreshadow", "volume": volume, "chapter": chapter})

    def query(self, query_text: str, n_results: int = 5) -> list[str]:
        """检索最相关的记忆（内存模式，文本重叠匹配）。"""
        if not self._fallback:
            return []
        query_words = set(query_text)
        scored = []
        for item in self._fallback[-100:]:
            overlap = len(query_words & set(item["text"]))
            if overlap > 0:
                scored.append((overlap, item["text"]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [text for _, text in scored[:n_results]]

    def get_context_for_chapter(self, volume: int, chapter: int, query_hint: str = "") -> str:
        """获取当前章节的上下文记忆。"""
        queries = [f"第{volume}卷第{chapter}章"]
        if query_hint:
            queries.append(query_hint)
        all_results = []
        for q in queries:
            all_results.extend(self.query(q, n_results=4))
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for r in all_results:
            key = r[:80]
            if key not in seen:
                seen.add(key)
                unique.append(r)
        if not unique:
            return ""
        return "## 相关记忆（从向量数据库检索）\n" + "\n".join(f"- {r}" for r in unique[:8])

    def stats(self) -> dict:
        return {"backend": "memory", "count": len(self._fallback)}
