import json
from agents.base import BaseAgent
from prompts.character import CHARACTER_SYSTEM, CHARACTER_USER_TEMPLATE


class CharacterAgent(BaseAgent):
    """人物与风格设计代理。"""
    name = "character"

    def design(self, outline: dict, style: str = "自动匹配", character_requirements: str = "无特殊要求") -> dict:
        user_message = CHARACTER_USER_TEMPLATE.format(
            outline=json.dumps(outline, ensure_ascii=False, indent=2),
            style=style, character_requirements=character_requirements,
        )
        response = self.run(CHARACTER_SYSTEM, user_message, temperature=0.8, max_tokens=16384)
        return self.parse_json(response)
