import json
from agents.base import BaseAgent
from prompts.editor import EDITOR_SYSTEM, EDITOR_USER_TEMPLATE


class EditorAgent(BaseAgent):
    name = "editor"

    def review(self, title: str, genre: str, volume_number: int, volume_title: str,
               chapter_number: int, chapter_title: str, content: str,
               characters: dict, writing_style: dict, bible_context: str = "") -> str:
        user_message = EDITOR_USER_TEMPLATE.format(
            title=title, genre=genre, volume_number=volume_number, volume_title=volume_title,
            chapter_number=chapter_number, chapter_title=chapter_title, content=content,
            characters=json.dumps(characters, ensure_ascii=False, indent=2),
            writing_style=json.dumps(writing_style, ensure_ascii=False, indent=2),
            bible_context=bible_context or "无",
        )
        return self.run(EDITOR_SYSTEM, user_message, temperature=0.4, max_tokens=4096)

    def review_stream(self, title: str, genre: str, volume_number: int, volume_title: str,
                      chapter_number: int, chapter_title: str, content: str,
                      characters: dict, writing_style: dict, bible_context: str = ""):
        user_message = EDITOR_USER_TEMPLATE.format(
            title=title, genre=genre, volume_number=volume_number, volume_title=volume_title,
            chapter_number=chapter_number, chapter_title=chapter_title, content=content,
            characters=json.dumps(characters, ensure_ascii=False, indent=2),
            writing_style=json.dumps(writing_style, ensure_ascii=False, indent=2),
            bible_context=bible_context or "无",
        )
        return self.run(EDITOR_SYSTEM, user_message, stream=True, temperature=0.4, max_tokens=4096)
