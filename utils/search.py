"""联网搜索模块 — 支持 Tavily / SearXNG。

提供统一的搜索接口，搜索结果可注入到 AI 写作上下文中。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchResult:
    title: str
    url: str
    content: str
    score: float = 1.0


class SearchEngine:
    """搜索后端基类。"""

    def __init__(self, config: dict):
        self.config = config

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        raise NotImplementedError

    def format_context(self, results: list[SearchResult]) -> str:
        """将搜索结果格式化为 LLM 可读的上下文字符串。"""
        if not results:
            return ""
        lines = ["\n## 联网搜索结果（供参考）"]
        for i, r in enumerate(results, 1):
            snippet = r.content[:500].replace("{", "{{").replace("}", "}}")
            lines.append(f"{i}. [{r.title}]({r.url})")
            lines.append(f"   {snippet}")
        return "\n".join(lines)


class TavilySearch(SearchEngine):
    """Tavily API 搜索后端。"""

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        try:
            from tavily import TavilyClient
        except ImportError:
            raise RuntimeError("请安装 tavily-python: pip install tavily-python")

        api_key = self.config.get("tavily_api_key", "")
        if not api_key:
            raise RuntimeError("Tavily API Key 未配置，请在「配置」页设置")

        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=max_results)

        results = []
        for item in response.get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", ""),
                score=item.get("score", 1.0),
            ))
        return results


class SearXNGSearch(SearchEngine):
    """SearXNG 自托管搜索后端。"""

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        import httpx

        base_url = self.config.get("searxng_base_url", "").rstrip("/")
        if not base_url:
            raise RuntimeError("SearXNG 地址未配置，请在「配置」页设置")

        try:
            resp = httpx.get(
                f"{base_url}/search",
                params={"q": query, "format": "json", "language": "zh-CN", "pageno": 1},
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f"SearXNG 请求失败: {e}")

        results = []
        for item in data.get("results", [])[:max_results]:
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", ""),
                score=1.0,
            ))
        return results


def get_search_engine(config: dict) -> SearchEngine:
    """根据配置获取搜索后端实例。"""
    provider = config.get("search_provider", "").lower()
    if provider == "tavily":
        return TavilySearch(config)
    elif provider == "searxng":
        return SearXNGSearch(config)
    else:
        raise RuntimeError(f"不支持的搜索提供商: {provider}（支持: tavily, searxng）")
