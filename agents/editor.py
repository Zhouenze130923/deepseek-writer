from agents.base import BaseAgent
from prompts.editor import (
    EDITOR_SYSTEM, EDITOR_USER_TEMPLATE,
    LOGIC_SYSTEM, STYLE_SYSTEM, FORESHADOW_EDITOR_SYSTEM,
)


class EditorAgent(BaseAgent):
    """冷血编辑——支持单一审查或三项专项并行审查。"""
    name = "editor"

    def _build_context(self, title, genre, volume_number, volume_title, chapter_number, chapter_title,
                       content, brief, bible_context):
        chars_list = brief.get("characters_brief", []) if brief else []
        chars_text = "\n".join(
            f"- {c.get('name','')}({c.get('role','')}): {c.get('core','')} 说话:{c.get('voice','')}"
            for c in chars_list
        )
        style_text = "\n".join(f"- {r}" for r in brief.get("style_rules", [])) if brief else ""
        world_text = "\n".join(f"- {r}" for r in brief.get("world_rules", [])) if brief else ""

        return {
            "title": title, "genre": genre,
            "volume_number": volume_number, "volume_title": volume_title,
            "chapter_number": chapter_number, "chapter_title": chapter_title,
            "content": content,
            "characters_brief": chars_text or "无",
            "style_rules": style_text or "无",
            "world_rules": world_text or "无",
            "bible_context": bible_context or "无",
        }

    def review(self, title, genre, volume_number, volume_title,
               chapter_number, chapter_title, content, brief, bible_context=""):
        ctx = self._build_context(title, genre, volume_number, volume_title,
                                  chapter_number, chapter_title, content, brief, bible_context)
        user_message = EDITOR_USER_TEMPLATE.format(**ctx)
        return self.run(EDITOR_SYSTEM, user_message, temperature=0.4, max_tokens=2048)

    def review_stream(self, title, genre, volume_number, volume_title,
                      chapter_number, chapter_title, content, brief, bible_context=""):
        ctx = self._build_context(title, genre, volume_number, volume_title,
                                  chapter_number, chapter_title, content, brief, bible_context)
        user_message = EDITOR_USER_TEMPLATE.format(**ctx)
        return self.run(EDITOR_SYSTEM, user_message, stream=True, temperature=0.4, max_tokens=2048)

    # --- Parallel triple-editor review ---

    def review_parallel(self, title, genre, volume_number, volume_title,
                        chapter_number, chapter_title, content, brief, bible_context="") -> str:
        """三项专项编辑并行审查，合并报告。"""
        ctx = self._build_context(title, genre, volume_number, volume_title,
                                  chapter_number, chapter_title, content, brief, bible_context)
        base_msg = EDITOR_USER_TEMPLATE.format(**ctx)

        import concurrent.futures

        def _call_logic():
            return self.run(LOGIC_SYSTEM,
                base_msg + "\n请只检查逻辑一致性、因果关系和设定矛盾。",
                stream=False, temperature=0.3, max_tokens=1024)

        def _call_style():
            return self.run(STYLE_SYSTEM,
                base_msg + "\n请只检查文笔质量、展示vs说教、对话辨识度。",
                stream=False, temperature=0.3, max_tokens=1024)

        def _call_foreshadow():
            return self.run(FORESHADOW_EDITOR_SYSTEM,
                base_msg + "\n请只检查伏笔处理、章末钩子、节奏。",
                stream=False, temperature=0.3, max_tokens=1024)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [
                pool.submit(_call_logic),
                pool.submit(_call_style),
                pool.submit(_call_foreshadow),
            ]
            logic_report = futures[0].result()
            style_report = futures[1].result()
            foreshadow_report = futures[2].result()

        return f"""## 🔍 三专项编辑联合审查

### 逻辑编辑（一致性/矛盾/因果）
{logic_report or '通过'}

### 风格编辑（文笔/展示/对话）
{style_report or '通过'}

### 伏笔编辑（线索/钩子/节奏）
{foreshadow_report or '通过'}
"""
