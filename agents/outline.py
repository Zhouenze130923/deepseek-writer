from agents.base import BaseAgent
from prompts.outline import OUTLINE_SYSTEM, OUTLINE_USER_TEMPLATE


class OutlineAgent(BaseAgent):
    """大纲生成代理。"""
    name = "outline"

    def generate(self, premise: str, template_guide: str = "") -> dict:
        user_message = OUTLINE_USER_TEMPLATE.format(
            premise=premise,
            template_guide=template_guide or "根据创意自动选择最合适的结构。",
        )
        response = self.run(OUTLINE_SYSTEM, user_message, temperature=0.7, max_tokens=16384)
        return self.parse_json(response)
