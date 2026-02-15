"""Utility tools for DenosysBot runtime capabilities."""

from denosysbot.tools.web import (
    WebSearchResult,
    build_url_context,
    build_web_context,
    extract_urls,
    normalize_duckduckgo_result_url,
    parse_duckduckgo_results,
    search_duckduckgo,
)

__all__ = [
    "WebSearchResult",
    "build_url_context",
    "build_web_context",
    "extract_urls",
    "normalize_duckduckgo_result_url",
    "parse_duckduckgo_results",
    "search_duckduckgo",
]
