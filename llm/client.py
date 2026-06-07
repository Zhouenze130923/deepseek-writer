from __future__ import annotations
from typing import Generator
from anthropic import Anthropic
from openai import OpenAI
from config import Config


class LLMClient:
    def __init__(self, config: Config):
        self.config = config
        self._anthropic_client = None
        self._openai_client = None

    @property
    def anthropic(self) -> Anthropic:
        if self._anthropic_client is None:
            self._anthropic_client = Anthropic(
                api_key=self.config.claude_api_key,
                timeout=120.0,
                max_retries=2,
            )
        return self._anthropic_client

    @property
    def openai(self) -> OpenAI:
        if self._openai_client is None:
            self._openai_client = OpenAI(
                api_key=self.config.deepseek_api_key,
                base_url=self.config.deepseek_base_url,
                timeout=120.0,           # 单次请求超时 2 分钟
                max_retries=2,            # 失败重试 2 次
            )
        return self._openai_client

    def chat(self, system: str, messages: list[dict], *, stream: bool = False,
             temperature: float | None = None, max_tokens: int | None = None):
        temp = temperature if temperature is not None else self.config.temperature
        max_tok = max_tokens if max_tokens is not None else self.config.max_tokens
        if self.config.provider == "claude":
            return self._chat_claude(system, messages, stream, temp, max_tok)
        return self._chat_deepseek(system, messages, stream, temp, max_tok)

    def _chat_claude(self, system, messages, stream, temperature, max_tokens):
        anthropic_messages = []
        for m in messages:
            role = "assistant" if m["role"] == "assistant" else "user"
            anthropic_messages.append({"role": role, "content": m["content"]})
        if stream:
            return self._stream_claude(system, anthropic_messages, temperature, max_tokens)
        response = self.anthropic.messages.create(
            model=self.config.claude_model, system=system, messages=anthropic_messages,
            temperature=temperature, max_tokens=max_tokens)
        return response.content[0].text

    def _stream_claude(self, system, messages, temperature, max_tokens):
        with self.anthropic.messages.stream(
            model=self.config.claude_model, system=system, messages=messages,
            temperature=temperature, max_tokens=max_tokens) as stream:
            for text in stream.text_stream:
                yield text

    def _chat_deepseek(self, system, messages, stream, temperature, max_tokens):
        openai_messages = [{"role": "system", "content": system}]
        for m in messages:
            openai_messages.append({"role": m["role"], "content": m["content"]})
        if stream:
            return self._stream_deepseek(openai_messages, temperature, max_tokens)
        response = self.openai.chat.completions.create(
            model=self.config.model, messages=openai_messages, temperature=temperature, max_tokens=max_tokens)
        return response.choices[0].message.content or ""

    def _stream_deepseek(self, messages, temperature, max_tokens):
        response = self.openai.chat.completions.create(
            model=self.config.model, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=True)
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
