from __future__ import annotations
import json
import re

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
        """从 LLM 回复中提取 JSON，自动修复截断。

        策略（按优先级）：
        1. 从 ```json 或 ``` 代码块中提取
        2. 直接解析完整响应
        3. 找到第一个 { 截取到最后一个 }
        4. 逐步修复截断（补引号、删多余逗号、补花括号/方括号）
        5. 尝试提取部分有效 JSON（去掉末尾不完整字段）
        """

        def _extract_code_block(text: str) -> str | None:
            """提取 markdown 代码块内的 JSON。"""
            for marker in ("```json", "```"):
                start_idx = text.find(marker)
                if start_idx < 0:
                    continue
                start_content = start_idx + len(marker)
                end_idx = text.find("```", start_content)
                if end_idx >= 0:
                    return text[start_content:end_idx].strip()
                # 没有关闭的代码块，取从 marker 到结尾
                return text[start_content:].strip()
            return None

        # 1) 尝试从代码块提取
        code_block = _extract_code_block(response)
        if code_block:
            try:
                return json.loads(code_block)
            except json.JSONDecodeError:
                response = code_block

        # 2) 尝试直接解析
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # 3) 找到 JSON 起始位置
        start = response.find("{")
        if start < 0:
            raise ValueError(f"Cannot find JSON object in response: {response[:200]}...")
        json_str = response[start:]

        # 4) 尝试用各种策略修复
        result = _try_repair_json(json_str)
        if result is not None:
            return result

        # 5) 如果已经修复了但还是失败，抛出详细的异常
        raise ValueError(f"JSON parse failed. Response length={len(response)}, "
                         f"JSON part length={len(json_str)}. "
                         f"First 300 chars: {response[:300]}...")


def _try_repair_json(s: str) -> dict | None:
    """尝试多种策略修复截断/损坏的 JSON。返回 dict 或 None。"""

    def _clean(text: str) -> str:
        text = _remove_trailing_backslash(text)
        text = _close_strings(text)
        text = _balance_json(text)
        # 移除多余的尾逗号（JSON 不允许尾逗号）
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        return text

    strategies = [
        # 0: 直接尝试
        lambda t: t,
        # 1: 关闭字符串 + 平衡括号
        lambda t: _clean(t),
        # 2: 去掉最后一个不完整键值对（从右向左找前一逗号截断）
        lambda t: _clean(t[:t.rfind(',')]) if ',' in t else _clean(t),
        # 3: 逐段截断 last comma (逆向多重查找)
        lambda t: _try_truncate_at_comma(t),
        # 4: 暴力截断末尾内容
        lambda t: _try_violent_truncate(t),
    ]

    for strategy in strategies:
        try:
            return json.loads(strategy(s))
        except json.JSONDecodeError:
            pass

    return None


def _try_truncate_at_comma(s: str) -> str:
    """从右向左在逗号位置截断，逐步删除不完整的字段。"""
    text = s
    for _ in range(15):
        rcomma = text.rfind(',')
        if rcomma < 0:
            break
        text = text[:rcomma]
        repaired = _clean_for_truncation(text)
        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            continue
    # 最后尝试：平衡到底
    return _clean_for_truncation(s)


def _clean_for_truncation(text: str) -> str:
    """清理截断文本：关括号、去尾逗号。"""
    text = _remove_trailing_backslash(text)
    text = _close_strings(text)
    text = _balance_json(text)
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    return text


def _try_violent_truncate(s: str) -> str:
    """暴力截断：逐步去掉末尾内容直到能解析。"""
    for pct in [0.95, 0.9, 0.85, 0.8, 0.7, 0.6, 0.5]:
        cut_pos = int(len(s) * pct)
        rcomma = s.rfind(',', 0, cut_pos)
        if rcomma > 0:
            test = _clean_for_truncation(s[:rcomma])
            try:
                json.loads(test)
                return test
            except json.JSONDecodeError:
                pass
    # 最后手段：只保留最基本的骨架
    return '{}'


def _close_strings(s: str) -> str:
    """补全被截断时未关闭的双引号字符串。"""
    in_str = False
    escaped = False
    last_unclosed_idx = -1
    for i, ch in enumerate(s):
        if escaped:
            escaped = False
            continue
        if ch == '\\':
            escaped = True
            continue
        if ch == '"':
            if not in_str:
                in_str = True
                last_unclosed_idx = i
            else:
                in_str = False
    if in_str:
        # 字符串未关闭 — 补上引号
        s += '"'
    return s


def _remove_trailing_backslash(s: str) -> str:
    """移除末尾的反斜杠（如果有），防止转义错误。"""
    while s.endswith('\\'):
        s = s[:-1]
    return s


def _balance_json(s: str) -> str:
    """补全未关闭的花括号和方括号。"""
    stack = []
    in_str = False
    escaped = False
    for i, ch in enumerate(s):
        if escaped:
            escaped = False
            continue
        if ch == '\\':
            escaped = True
            continue
        if ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == '{':
                stack.append('}')
            elif ch == '[':
                stack.append(']')
            elif ch == '}':
                if stack and stack[-1] == '}':
                    stack.pop()
            elif ch == ']':
                if stack and stack[-1] == ']':
                    stack.pop()
    return s + ''.join(reversed(stack))
