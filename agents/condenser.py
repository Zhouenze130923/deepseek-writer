from __future__ import annotations
from typing import TYPE_CHECKING

from agents.base import BaseAgent
if TYPE_CHECKING:
    from config import Config
    from llm.client import LLMClient


class CondenserAgent(BaseAgent):
    name = "condenser"

    def __init__(self, client: LLMClient | None = None, config: Config | None = None):
        if client is not None and config is not None:
            super().__init__(client, config)
        else:
            # 无 LLM 模式：纯字符串处理（兼容旧调用方式）
            self.client = None
            self.config = None
            self.history = []

    def condense(self, outline: dict, characters: dict, writing_style: dict) -> dict:
        return self._condense_quick(outline, characters, writing_style)

    def _condense_quick(self, outline: dict, characters: dict, writing_style: dict) -> dict:
        chars_brief = []
        for c in characters.get("characters", []):
            tags = (c.get("quirks", []) or [])[:2]
            chars_brief.append({
                "name": c.get("name", ""), "role": c.get("role", ""),
                "core": f"{c.get('personality','')[:60]}，动机：{c.get('motivation','')[:40]}",
                "voice": c.get("speech_style", "")[:60], "tags": tags,
            })

        volume_plan = []
        for v in outline.get("volumes", []):
            chapters = []
            for ch in v.get("chapters", []):
                chapters.append({
                    "ch": ch.get("chapter_number", 0), "title": ch.get("chapter_title", ""),
                    "must_happen": ch.get("synopsis", "")[:120], "pov": ch.get("pov_character", ""),
                })
            volume_plan.append({
                "volume": v.get("volume_number", 0), "title": v.get("volume_title", ""),
                "goal": v.get("synopsis", "")[:120], "chapters": chapters,
            })

        ws = characters.get("writing_style", {})
        style_rules = [
            f"叙事: {ws.get('narrative_mode','第三人称')}", f"节奏: {ws.get('pace','中速')}",
            f"基调: {ws.get('tone','')}", f"句式: {ws.get('sentence_style','')}",
            f"对话占比: {ws.get('dialogue_ratio','中')}",
        ]
        for feat in ws.get("language_features", [])[:3]:
            style_rules.append(f"特点: {feat}")

        wb = characters.get("world_building", {})
        world_rules = wb.get("rules", [])[:10]

        continuity = ""
        if characters.get("style_reference", {}).get("style_notes"):
            continuity = characters["style_reference"]["style_notes"][:200]

        return {
            "title": outline.get("title", ""), "genre": outline.get("genre", ""),
            "tone": outline.get("tone", ""), "characters_brief": chars_brief,
            "volume_plan": volume_plan, "style_rules": style_rules,
            "world_rules": world_rules, "continuity_notes": continuity,
        }

    def condense_with_llm(self, outline: dict, characters: dict, writing_style: dict) -> dict:
        """使用 LLM 生成更精炼的写作简报（保留字符串处理版本的回退）。"""
        if self.client is None:
            return self._condense_quick(outline, characters, writing_style)

        prompt = f"""你是一个小说写作压缩助手。根据以下信息，生成一个精炼的写作简报。

小说标题: {outline.get('title','')}
类型: {outline.get('genre','')}
基调: {outline.get('tone','')}

关键角色:
"""
        for c in characters.get("characters", [])[:4]:
            prompt += f"- {c.get('name','')}({c.get('role','')}): {c.get('personality','')[:80]}\n"

        prompt += f"""
写作风格: {json.dumps(characters.get('writing_style', {}), ensure_ascii=False)[:200]}
世界观规则: {json.dumps(characters.get('world_building', {}).get('rules', [])[:5], ensure_ascii=False)}

卷计划:
"""
        for v in outline.get("volumes", [])[:3]:
            chs = [f"第{c['chapter_number']}章 {c['chapter_title']}" for c in v.get("chapters", [])[:5]]
            prompt += f"第{v['volume_number']}卷「{v['volume_title']}」: {', '.join(chs)}\n"

        prompt += "\n请用 JSON 格式输出：{\"characters_brief\": [...], \"style_rules\": [...], \"world_rules\": [...], \"continuity_notes\": \"...\"}"

        try:
            response = self.client.chat(
                "你是一个专业的小说写作辅助AI，输出精简JSON。",
                [{"role": "user", "content": prompt}],
                stream=False, temperature=0.5, max_tokens=2048,
            )
            import json
            result = json.loads(response) if isinstance(response, str) else response
            # 补充字段
            result["title"] = outline.get("title", "")
            result["genre"] = outline.get("genre", "")
            result["tone"] = outline.get("tone", "")
            result["volume_plan"] = self._condense_quick(outline, characters, writing_style)["volume_plan"]
            return result
        except Exception:
            return self._condense_quick(outline, characters, writing_style)
