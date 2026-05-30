from agents.base import BaseAgent
from prompts.editor import EDITOR_SYSTEM, EDITOR_USER_TEMPLATE


class EditorAgent(BaseAgent):
    name = "editor"

    def _build_context(self, title, genre, volume_number, volume_title, chapter_number, chapter_title,
                       content, brief, bible_context):
        # Use condensed brief — same format as writer, much cheaper than full JSON
        chars_list = brief.get("characters_brief", []) if brief else []
        chars_text = "\n".join(
            f"- {c.get('name','')}({c.get('role','')}): {c.get('core','')} 说话:{c.get('voice','')}"
            for c in chars_list
        )
        style_text = "\n".join(f"- {r}" for r in brief.get("style_rules", [])) if brief else ""
        world_text = "\n".join(f"- {r}" for r in brief.get("world_rules", [])) if brief else ""

        return EDITOR_USER_TEMPLATE.format(
            title=title, genre=genre,
            volume_number=volume_number, volume_title=volume_title,
            chapter_number=chapter_number, chapter_title=chapter_title,
            content=content,
            characters_brief=chars_text or "无",
            style_rules=style_text or "无",
            world_rules=world_text or "无",
            bible_context=bible_context or "无",
        )

    def review(self, title, genre, volume_number, volume_title,
               chapter_number, chapter_title, content, brief, bible_context=""):
        user_message = self._build_context(title, genre, volume_number, volume_title,
                                           chapter_number, chapter_title, content, brief, bible_context)
        return self.run(EDITOR_SYSTEM, user_message, temperature=0.4, max_tokens=2048)

    def review_stream(self, title, genre, volume_number, volume_title,
                      chapter_number, chapter_title, content, brief, bible_context=""):
        user_message = self._build_context(title, genre, volume_number, volume_title,
                                           chapter_number, chapter_title, content, brief, bible_context)
        return self.run(EDITOR_SYSTEM, user_message, stream=True, temperature=0.4, max_tokens=2048)
