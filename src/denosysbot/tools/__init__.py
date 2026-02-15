"""Utility tools for DenosysBot runtime capabilities."""

from denosysbot.tools.web import (
    WebSearchResult,
    build_web_context,
    normalize_duckduckgo_result_url,
    parse_duckduckgo_results,
    search_duckduckgo,
)

__all__ = [
    "WebSearchResult",
    "build_web_context",
    "normalize_duckduckgo_result_url",
    "parse_duckduckgo_results",
    "search_duckduckgo",
]
