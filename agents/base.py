from __future__ import annotations
import json

from llm.client import LLMClient
from config import Config


class BaseAgent:
    """代理基类。"""

    name: str = "base"

    def __init__(self, client: LLMClient, config: Config):
        self.client = client
        self.config = config
        self.history: list[dict] = []

    def run(self, system: str, user_message: str, *, stream: bool = False,
            temperature: float | None = None, max_tokens: int | None = None):
        messages = [{"role": "user", "content": user_message}]
        return self.client.chat(system, messages, stream=stream, temperature=temperature, max_tokens=max_tokens)

    def chat(self, user_message: str, *, stream: bool = False) -> str:
        self.history.append({"role": "user", "content": user_message})
        response = self.client.chat("", self.history, stream=stream)
        if not stream:
            self.history.append({"role": "assistant", "content": response})
        return response

    def clear_history(self):
        self.history = []

    @staticmethod
    def parse_json(response: str) -> dict:
        """从 LLM 回复中提取 JSON，自动修复截断。"""
        if "```json" in response:
            start = response.index("```json") + 7
            remaining = response[start:]
            end_marker = remaining.find("```")
            if end_marker >= 0:
                return json.loads(remaining[:end_marker])
            response = remaining
        elif "```" in response:
            start = response.index("```") + 3
            remaining = response[start:]
            end_marker = remaining.find("```")
            if end_marker >= 0:
                return json.loads(remaining[:end_marker])
            response = remaining

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        start = response.find("{")
        if start < 0:
            raise ValueError(f"Cannot find JSON in response: {response[:200]}...")
        json_str = response[start:]

        # 快速校验：如果已经是合法 JSON，直接返回
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        for _ in range(5):
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                msg = str(e)
                if "Unterminated string" in msg:
                    json_str += '"'
                    continue
                if "Expecting" in msg or "Extra data" in msg:
                    err_pos = e.pos if hasattr(e, 'pos') else len(json_str) - 1
                    if err_pos > 0:
                        cut = json_str.rfind(',', 0, err_pos)
                        if cut > 0:
                            json_str = json_str[:cut + 1]
                    json_str = _balance_json(json_str)
                    continue
                break

        raise ValueError(f"JSON parse failed after 5 retries. First 300 chars: {response[:300]}...")


def _balance_json(s: str) -> str:
    stack = []
    in_str = False
    prev = ''
    for ch in s:
        if ch == '"' and prev != '\\':
            in_str = not in_str
        elif not in_str:
            if ch == '{': stack.append('}')
            elif ch == '}':
                if stack and stack[-1] == '}': stack.pop()
            elif ch == '[': stack.append(']')
            elif ch == ']':
                if stack and stack[-1] == ']': stack.pop()
        prev = ch
    return s + ''.join(reversed(stack))
