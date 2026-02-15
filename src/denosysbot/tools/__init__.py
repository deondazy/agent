"""Utility tools for DenosysBot runtime capabilities."""

from denosysbot.tools.web import (
    CrawledPage,
    WebSearchResult,
    build_crawl_context,
    build_url_context,
    build_web_context,
    crawl_docs_site,
    extract_urls,
    normalize_duckduckgo_result_url,
    parse_duckduckgo_results,
    search_duckduckgo,
)

__all__ = [
    "CrawledPage",
    "WebSearchResult",
    "build_crawl_context",
    "build_url_context",
    "build_web_context",
    "crawl_docs_site",
    "extract_urls",
    "normalize_duckduckgo_result_url",
    "parse_duckduckgo_results",
    "search_duckduckgo",
]
