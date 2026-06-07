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
            "search_context": kwargs.get("search_context", ""),
            "user_suggestions": kwargs.get("user_suggestions", "无"),
            **kwargs,
        }

    def write_chapter(self, brief: dict, volume_number: int, volume_title: str, volume_goal: str,
                      chapter_number: int, chapter_title: str, must_happen: str, pov: str,
                      previous_context: str = "", plant_foreshadowing: str = "",
                      resolve_foreshadowing: str = "", bible_context: str = "",
                      search_context: str = "", user_suggestions: str = "") -> str:
        ctx = self._build_context(brief, volume_number=volume_number, volume_title=volume_title,
                                  volume_goal=volume_goal, chapter_number=chapter_number,
                                  chapter_title=chapter_title, must_happen=must_happen, pov=pov,
                                  previous_context=previous_context, plant_foreshadowing=plant_foreshadowing,
                                  resolve_foreshadowing=resolve_foreshadowing, bible_context=bible_context,
                                  search_context=search_context, user_suggestions=user_suggestions)
        response = self.run(WRITER_SYSTEM, WRITER_CHAPTER_TEMPLATE.format(**ctx), temperature=0.85, max_tokens=8192)
        return self._extract_content(response)

    def write_chapter_stream(self, brief: dict, volume_number: int, volume_title: str, volume_goal: str,
                             chapter_number: int, chapter_title: str, must_happen: str, pov: str,
                             previous_context: str = "", plant_foreshadowing: str = "",
                             resolve_foreshadowing: str = "", bible_context: str = "",
                             search_context: str = "", user_suggestions: str = ""):
        ctx = self._build_context(brief, volume_number=volume_number, volume_title=volume_title,
                                  volume_goal=volume_goal, chapter_number=chapter_number,
                                  chapter_title=chapter_title, must_happen=must_happen, pov=pov,
                                  previous_context=previous_context, plant_foreshadowing=plant_foreshadowing,
                                  resolve_foreshadowing=resolve_foreshadowing, bible_context=bible_context,
                                  search_context=search_context, user_suggestions=user_suggestions)
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

    def write_parallel(self, brief: dict, volume_number: int, volume_title: str, volume_goal: str,
                         chapter_number: int, chapter_title: str, must_happen: str, pov: str,
                         previous_context: str = "", search_context: str = "",
                         user_suggestions: str = "", bible_context: str = "", num_scenes: int = 3) -> str:
        """多子代理并行写作：将章节按场景拆成 num_scenes 段，每段由独立代理写完后合并。"""
        import concurrent.futures

        def _write_scene(scene_idx: int, scene_count: int):
            """单个子代理写一段场景。"""
            writer = WriterAgent(self.client, self.config)
            if scene_idx == 0:
                ctx_hint = f"本章开头，衔接: {previous_context}"
            elif scene_idx == scene_count - 1:
                ctx_hint = f"本章结尾，需要制造章末钩子"
            else:
                ctx_hint = f"本章中间第{scene_idx + 1}段"

            ctx = self._build_context(brief,
                volume_number=volume_number, volume_title=volume_title,
                volume_goal=volume_goal, chapter_number=chapter_number,
                chapter_title=chapter_title, must_happen=must_happen, pov=pov,
                previous_context=f"{ctx_hint} | {previous_context}",
                plant_foreshadowing="自然植入",
                resolve_foreshadowing="",
                bible_context=bible_context,
                search_context=search_context,
                user_suggestions=user_suggestions,
            )
            ctx["must_happen"] = f"[{ctx_hint}] {must_happen}"
            response = writer.run(WRITER_SYSTEM, WRITER_CHAPTER_TEMPLATE.format(**ctx),
                                  temperature=0.85, max_tokens=4096)
            return WriterAgent._extract_content(response)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_scenes) as pool:
            future_map = {pool.submit(_write_scene, i, num_scenes): i for i in range(num_scenes)}
            scene_results = {}
            for future in concurrent.futures.as_completed(future_map):
                idx = future_map[future]
                try:
                    scene_results[idx] = future.result(timeout=120)
                except Exception as e:
                    scene_results[idx] = f"[场景{idx + 1}写作异常: {e}]"

        # 按顺序合并
        scenes = [scene_results[i] for i in range(num_scenes)]
        return "\n\n".join(scenes)

    @staticmethod
    def _extract_content(response: str) -> str:
        """去除 AI 可能遗留的包裹标记，返回纯正文。"""
        text = response.strip()
        for marker in ["【正文开始】", "【正文结束】", "【正文开始】", "【正文结束】"]:
            text = text.replace(marker, "")
        # 清除 AI 可能仍输出的旧格式标记
        for old in ["【正文开始】", "【正文结束】"]:
            text = text.replace(old, "")
        return text.strip()

    @staticmethod
    def _stream_extract_content(response_stream):
        """流式提取，移除可能的包裹标记。"""
        buffer = ""
        for chunk in response_stream:
            chunk = chunk.replace("【正文开始】", "").replace("【正文结束】", "")
            buffer += chunk
            yield chunk
        if buffer.strip():
            return
