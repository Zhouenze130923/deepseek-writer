from agents.base import BaseAgent
from prompts.writer import (
    WRITER_SYSTEM, WRITER_CHAPTER_TEMPLATE, WRITER_REVISE_TEMPLATE, WRITER_CONTINUE_TEMPLATE,
)


class WriterAgent(BaseAgent):
    """写作执行代理。"""
    name = "writer"

    def _build_context(self, brief, **kwargs):
        chars_list = brief.get("characters_brief", [])
        chars_text = "\n".join(
            f"- {c['name']}({c['role']}): {c['core']} 说话:{c['voice']} [{', '.join(c.get('tags',[]))}]"
            for c in chars_list
        )
        return {
            "title": brief.get("title", ""), "genre": brief.get("genre", ""),
            "tone": brief.get("tone", ""), "characters_brief": chars_text,
            "style_rules": "\n".join(f"- {r}" for r in brief.get("style_rules", [])),
            "world_rules": "\n".join(f"- {r}" for r in brief.get("world_rules", [])),
            "continuity_notes": brief.get("continuity_notes", ""),
            "previous_context": kwargs.get("previous_context", "无"),
            "pov": kwargs.get("pov", ""),
            "plant_foreshadowing": kwargs.get("plant_foreshadowing", "无"),
            "resolve_foreshadowing": kwargs.get("resolve_foreshadowing", "无"),
            "bible_context": kwargs.get("bible_context", "无"),
            **kwargs,
        }

    def write_chapter(self, brief: dict, volume_number: int, volume_title: str, volume_goal: str,
                      chapter_number: int, chapter_title: str, must_happen: str, pov: str,
                      previous_context: str = "", plant_foreshadowing: str = "",
                      resolve_foreshadowing: str = "", bible_context: str = "") -> str:
        ctx = self._build_context(brief, volume_number=volume_number, volume_title=volume_title,
                                  volume_goal=volume_goal, chapter_number=chapter_number,
                                  chapter_title=chapter_title, must_happen=must_happen, pov=pov,
                                  previous_context=previous_context, plant_foreshadowing=plant_foreshadowing,
                                  resolve_foreshadowing=resolve_foreshadowing, bible_context=bible_context)
        response = self.run(WRITER_SYSTEM, WRITER_CHAPTER_TEMPLATE.format(**ctx), temperature=0.85, max_tokens=8192)
        return self._extract_content(response)

    def write_chapter_stream(self, brief: dict, volume_number: int, volume_title: str, volume_goal: str,
                             chapter_number: int, chapter_title: str, must_happen: str, pov: str,
                             previous_context: str = "", plant_foreshadowing: str = "",
                             resolve_foreshadowing: str = "", bible_context: str = ""):
        ctx = self._build_context(brief, volume_number=volume_number, volume_title=volume_title,
                                  volume_goal=volume_goal, chapter_number=chapter_number,
                                  chapter_title=chapter_title, must_happen=must_happen, pov=pov,
                                  previous_context=previous_context, plant_foreshadowing=plant_foreshadowing,
                                  resolve_foreshadowing=resolve_foreshadowing, bible_context=bible_context)
        response = self.run(WRITER_SYSTEM, WRITER_CHAPTER_TEMPLATE.format(**ctx), stream=True, temperature=0.85, max_tokens=8192)
        yield from self._stream_extract_content(response)

    def revise_chapter(self, brief: dict, original_content: str, editor_report: str) -> str:
        chars_list = brief.get("characters_brief", [])
        chars_text = "\n".join(f"- {c['name']}({c['role']}): {c['core']} 说话:{c['voice']}" for c in chars_list)
        style_rules = "\n".join(f"- {r}" for r in brief.get("style_rules", []))
        world_rules = "\n".join(f"- {r}" for r in brief.get("world_rules", []))
        user_message = WRITER_REVISE_TEMPLATE.format(
            characters_brief=chars_text, style_rules=style_rules, world_rules=world_rules,
            original_content=original_content, editor_report=editor_report,
        )
        response = self.run(WRITER_SYSTEM, user_message, temperature=0.7, max_tokens=8192)
        return self._extract_content(response)

    def revise_chapter_stream(self, brief: dict, original_content: str, editor_report: str):
        chars_list = brief.get("characters_brief", [])
        chars_text = "\n".join(f"- {c['name']}({c['role']}): {c['core']} 说话:{c['voice']}" for c in chars_list)
        style_rules = "\n".join(f"- {r}" for r in brief.get("style_rules", []))
        world_rules = "\n".join(f"- {r}" for r in brief.get("world_rules", []))
        user_message = WRITER_REVISE_TEMPLATE.format(
            characters_brief=chars_text, style_rules=style_rules, world_rules=world_rules,
            original_content=original_content, editor_report=editor_report,
        )
        response = self.run(WRITER_SYSTEM, user_message, stream=True, temperature=0.7, max_tokens=8192)
        yield from self._stream_extract_content(response)

    @staticmethod
    def _extract_content(response: str) -> str:
        if "【正文开始】" in response and "【正文结束】" in response:
            start = response.index("【正文开始】") + 6
            end = response.index("【正文结束】")
            return response[start:end].strip()
        return response.strip()

    @staticmethod
    def _stream_extract_content(response_stream):
        """从流式响应中提取【正文开始】和【正文结束】之间的内容。"""
        buffer = ""
        in_content = False
        for chunk in response_stream:
            buffer += chunk
            if "【正文开始】" in buffer and not in_content:
                in_content = True
                idx = buffer.index("【正文开始】") + 6
                buffer = buffer[idx:]
            if "【正文结束】" in buffer:
                end_idx = buffer.index("【正文结束】")
                yield buffer[:end_idx]
                return
            if in_content:
                yield_buffer = buffer
                buffer = ""
                if yield_buffer:
                    yield yield_buffer
        if buffer:
            if "【正文结束】" in buffer:
                buffer = buffer[: buffer.index("【正文结束】")]
            if buffer.strip():
                yield buffer
