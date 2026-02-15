"""Lightweight web search and context extraction helpers."""

from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse
import re

import httpx

URL_PATTERN = re.compile(r"https?://[^\s)>\]\"']+")
RESULT_ANCHOR_PATTERN = re.compile(
    r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    flags=re.IGNORECASE | re.DOTALL,
)
TAG_PATTERN = re.compile(r"<[^>]+>")
SCRIPT_STYLE_PATTERN = re.compile(r"<(script|style)\b.*?>.*?</\1>", flags=re.IGNORECASE | re.DOTALL)
WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class WebSearchResult:
    title: str
    url: str
    excerpt: str = ""


def extract_urls(text: str) -> tuple[str, ...]:
    """Extract HTTP(S) URLs from free-form user text."""

    discovered: list[str] = []
    for raw in URL_PATTERN.findall(text):
        cleaned = raw.rstrip(".,;:!?")
        if cleaned and cleaned not in discovered:
            discovered.append(cleaned)
    return tuple(discovered)


def normalize_duckduckgo_result_url(raw_url: str) -> str:
    """Normalize DuckDuckGo redirect URLs to direct links."""

    url = unescape(raw_url.strip())
    if url.startswith("//"):
        url = f"https:{url}"

    parsed = urlparse(url)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        query = parse_qs(parsed.query)
        redirected = query.get("uddg")
        if redirected:
            return unquote(redirected[0])
    return url


def parse_duckduckgo_results(html: str) -> list[WebSearchResult]:
    """Extract search result titles + URLs from DuckDuckGo HTML."""

    results: list[WebSearchResult] = []
    for href, raw_title in RESULT_ANCHOR_PATTERN.findall(html):
        normalized_url = normalize_duckduckgo_result_url(href)
        cleaned_title = _strip_tags(raw_title)
        if not cleaned_title or not normalized_url:
            continue
        results.append(WebSearchResult(title=cleaned_title, url=normalized_url))
    return results


def search_duckduckgo(
    query: str,
    *,
    max_results: int = 5,
    timeout_seconds: float = 15.0,
    http_client: httpx.Client | None = None,
) -> list[WebSearchResult]:
    """Run a real internet search against DuckDuckGo HTML endpoint."""

    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    if http_client is None:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            return search_duckduckgo(
                cleaned_query,
                max_results=max_results,
                timeout_seconds=timeout_seconds,
                http_client=client,
            )

    response = http_client.get(
        "https://duckduckgo.com/html/",
        params={"q": cleaned_query},
        headers={"User-Agent": "denosysbot/0.1 (+https://example.local)"},
    )
    response.raise_for_status()
    results = parse_duckduckgo_results(response.text)
    return results[:max(1, max_results)]


def build_web_context(
    query: str,
    *,
    max_results: int = 3,
    max_excerpt_chars: int = 280,
    http_client: httpx.Client | None = None,
) -> tuple[str, list[WebSearchResult]]:
    """Build compact prompt context from live web results."""

    results = search_duckduckgo(query, max_results=max_results, http_client=http_client)
    if not results:
        return "", []

    enriched: list[WebSearchResult] = []
    for result in results:
        excerpt = fetch_web_excerpt(result.url, max_chars=max_excerpt_chars, http_client=http_client)
        enriched.append(WebSearchResult(title=result.title, url=result.url, excerpt=excerpt))

    lines = [f"Live web results for: {query.strip()}"]
    for index, result in enumerate(enriched, start=1):
        lines.append(f"{index}. {result.title} - {result.url}")
        if result.excerpt:
            lines.append(f"   Excerpt: {result.excerpt}")
    return "\n".join(lines), enriched


def build_url_context(
    urls: tuple[str, ...],
    *,
    max_excerpt_chars: int = 2200,
    http_client: httpx.Client | None = None,
) -> tuple[str, list[WebSearchResult]]:
    """Build context from explicit URLs instead of search queries."""

    unique_urls: list[str] = []
    for url in urls:
        cleaned = url.strip()
        if cleaned and cleaned not in unique_urls:
            unique_urls.append(cleaned)

    if not unique_urls:
        return "", []

    results: list[WebSearchResult] = []
    lines = ["Live URL references:"]
    for index, url in enumerate(unique_urls, start=1):
        excerpt = fetch_web_excerpt(url, max_chars=max_excerpt_chars, http_client=http_client)
        result = WebSearchResult(title=urlparse(url).netloc or "source", url=url, excerpt=excerpt)
        results.append(result)
        lines.append(f"{index}. {url}")
        if excerpt:
            lines.append(f"   Excerpt: {excerpt}")
    return "\n".join(lines), results


def fetch_web_excerpt(
    url: str,
    *,
    max_chars: int = 280,
    timeout_seconds: float = 12.0,
    http_client: httpx.Client | None = None,
) -> str:
    """Fetch a URL and return a compact plain-text excerpt."""

    if http_client is None:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            return fetch_web_excerpt(
                url,
                max_chars=max_chars,
                timeout_seconds=timeout_seconds,
                http_client=client,
            )

    try:
        response = http_client.get(url, headers={"User-Agent": "denosysbot/0.1 (+https://example.local)"})
        response.raise_for_status()
    except (httpx.HTTPError, ValueError):
        return ""

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        return ""

    text = SCRIPT_STYLE_PATTERN.sub(" ", response.text)
    text = _strip_tags(text)
    text = WHITESPACE_PATTERN.sub(" ", text).strip()
    if not text:
        return ""
    return text if len(text) <= max_chars else f"{text[:max_chars].rstrip()}..."


def _strip_tags(raw: str) -> str:
    return unescape(TAG_PATTERN.sub("", raw)).strip()
