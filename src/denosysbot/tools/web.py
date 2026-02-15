"""Lightweight web search and context extraction helpers."""

from dataclasses import dataclass
from html import unescape
from collections import deque
from urllib.parse import parse_qs, unquote, urldefrag, urljoin, urlparse, urlunparse
import re
import time

import httpx

URL_PATTERN = re.compile(r"https?://[^\s)>\]\"']+")
HREF_PATTERN = re.compile(r'<a[^>]+href=["\']([^"\']+)["\']', flags=re.IGNORECASE)
TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", flags=re.IGNORECASE | re.DOTALL)
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


@dataclass(frozen=True, slots=True)
class CrawledPage:
    url: str
    title: str
    excerpt: str
    depth: int
    markdown: str = ""
    headings: tuple[str, ...] = ()
    code_blocks: tuple[str, ...] = ()


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


def crawl_docs_site(
    start_url: str,
    *,
    max_pages: int = 16,
    max_depth: int = 2,
    max_excerpt_chars: int = 2200,
    timeout_seconds: float = 12.0,
    http_client: httpx.Client | None = None,
) -> list[CrawledPage]:
    """Crawl documentation pages within the same site/prefix page-by-page."""

    parsed_start = urlparse(start_url.strip())
    if parsed_start.scheme not in {"http", "https"} or not parsed_start.netloc:
        return []

    root_url = _canonical_url(start_url)
    if not root_url:
        return []

    if http_client is None:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            return crawl_docs_site(
                root_url,
                max_pages=max_pages,
                max_depth=max_depth,
                max_excerpt_chars=max_excerpt_chars,
                timeout_seconds=timeout_seconds,
                http_client=client,
            )

    start_prefix = _derive_docs_prefix(urlparse(root_url).path)
    start_host = urlparse(root_url).netloc

    queue: deque[tuple[str, int]] = deque([(root_url, 0)])
    visited: set[str] = set()
    crawled: list[CrawledPage] = []

    while queue and len(crawled) < max(1, max_pages):
        current_url, depth = queue.popleft()
        if current_url in visited or depth > max_depth:
            continue
        visited.add(current_url)

        html, content_type = _fetch_page_html(current_url, http_client=http_client)
        if not html:
            continue

        normalized_html = html.lower()
        if (
            "text/html" not in content_type
            and "application/xhtml+xml" not in content_type
            and "<html" not in normalized_html
        ):
            continue

        title = _extract_html_title(html) or urlparse(current_url).path.strip("/") or current_url
        markdown = _extract_markdown_content(html, url=current_url, max_chars=max_excerpt_chars * 4)
        excerpt = _extract_plain_excerpt(html, max_chars=max_excerpt_chars)
        headings = _extract_headings(html)
        code_blocks = _extract_code_blocks(html)
        crawled.append(
            CrawledPage(
                url=current_url,
                title=title,
                excerpt=excerpt,
                depth=depth,
                markdown=markdown,
                headings=headings,
                code_blocks=code_blocks,
            )
        )

        if depth >= max_depth:
            continue

        for discovered_url in _extract_html_links(html, current_url):
            if discovered_url in visited:
                continue
            parsed = urlparse(discovered_url)
            if parsed.netloc != start_host:
                continue
            if not _path_matches_prefix(parsed.path, start_prefix):
                continue
            queue.append((discovered_url, depth + 1))

    return crawled


def build_crawl_context(
    pages: list[CrawledPage],
    *,
    max_excerpt_chars: int = 700,
) -> tuple[str, list[CrawledPage]]:
    """Build prompt context from crawled documentation pages."""

    if not pages:
        return "", []

    lines = ["Crawled documentation pages:"]
    for index, page in enumerate(pages, start=1):
        lines.append(f"{index}. {page.url}")
        if page.title:
            lines.append(f"   Title: {page.title}")
        if page.excerpt:
            clipped = page.excerpt if len(page.excerpt) <= max_excerpt_chars else f"{page.excerpt[:max_excerpt_chars].rstrip()}..."
            lines.append(f"   Excerpt: {clipped}")
    return "\n".join(lines), pages


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


def _extract_html_links(html: str, base_url: str) -> tuple[str, ...]:
    links: list[str] = []

    try:
        from bs4 import BeautifulSoup
    except ImportError:  # pragma: no cover - optional dependency
        BeautifulSoup = None

    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "lxml")
        for anchor in soup.find_all("a"):
            href = anchor.get("href")
            if not isinstance(href, str):
                continue
            absolute = urljoin(base_url, unescape(href).strip())
            canonical = _canonical_url(absolute)
            if canonical and canonical not in links:
                links.append(canonical)
        return tuple(links)

    for raw_href in HREF_PATTERN.findall(html):
        absolute = urljoin(base_url, unescape(raw_href).strip())
        canonical = _canonical_url(absolute)
        if canonical and canonical not in links:
            links.append(canonical)
    return tuple(links)


def _fetch_page_html(
    url: str,
    *,
    http_client: httpx.Client,
) -> tuple[str, str]:
    response: httpx.Response | None = None
    user_agents = (
        "denosysbot/0.1 (+https://example.local)",
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    for attempt, user_agent in enumerate(user_agents, start=1):
        try:
            response = http_client.get(url, headers={"User-Agent": user_agent})
            response.raise_for_status()
            break
        except httpx.HTTPError:
            response = None
            if attempt < len(user_agents):
                time.sleep(0.25)

    if response is None:
        rendered = _render_with_playwright(url)
        if rendered:
            return rendered, "text/html"
        return "", ""

    content_type = response.headers.get("content-type", "")
    html = response.text

    if _should_try_browser_render(content_type, html):
        rendered = _render_with_playwright(url)
        if rendered:
            return rendered, "text/html"

    return html, content_type


def _should_try_browser_render(content_type: str, html: str) -> bool:
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        return False
    lowered = html.lower()
    if len(lowered.strip()) < 500:
        return True
    return "__next" in lowered or "id=\"app\"" in lowered or "data-hydration" in lowered


def _render_with_playwright(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover - optional dependency
        return ""

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            content = page.content()
            browser.close()
            return content or ""
    except Exception:  # pragma: no cover - browser/runtime variability
        return ""


def _canonical_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        return ""
    no_fragment, _fragment = urldefrag(cleaned)
    parsed = urlparse(no_fragment)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def _derive_docs_prefix(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if not parts:
        return "/"

    if "docs" in parts:
        docs_idx = parts.index("docs")
        if docs_idx + 1 < len(parts):
            return f"/{'/'.join(parts[: docs_idx + 2])}/"
        return f"/{'/'.join(parts[: docs_idx + 1])}/"

    if len(parts) >= 2:
        return f"/{'/'.join(parts[:-1])}/"
    return f"/{parts[0]}/"


def _path_matches_prefix(path: str, prefix: str) -> bool:
    normalized_path = f"{path.rstrip('/')}/" if path not in {"", "/"} else "/"
    normalized_prefix = prefix if prefix.endswith("/") else f"{prefix}/"
    return normalized_path.startswith(normalized_prefix)


def _extract_html_title(html: str) -> str:
    match = TITLE_PATTERN.search(html)
    if not match:
        return ""
    return _strip_tags(match.group(1))


def _extract_plain_excerpt(html: str, *, max_chars: int) -> str:
    text = SCRIPT_STYLE_PATTERN.sub(" ", html)
    text = _strip_tags(text)
    text = WHITESPACE_PATTERN.sub(" ", text).strip()
    if not text:
        return ""
    return text if len(text) <= max_chars else f"{text[:max_chars].rstrip()}..."


def _extract_markdown_content(html: str, *, url: str, max_chars: int) -> str:
    try:
        import trafilatura
    except ImportError:  # pragma: no cover - optional dependency
        trafilatura = None

    markdown = ""
    if trafilatura is not None:
        try:
            extracted = trafilatura.extract(
                html,
                url=url,
                output_format="markdown",
                include_links=True,
                include_formatting=True,
                include_tables=True,
                favor_precision=True,
            )
            if isinstance(extracted, str):
                markdown = extracted.strip()
        except Exception:  # pragma: no cover - parser variability
            markdown = ""

    if not markdown:
        try:
            from markdownify import markdownify
        except ImportError:  # pragma: no cover - optional dependency
            markdownify = None

        if markdownify is not None:
            try:
                converted = markdownify(html, heading_style="ATX")
                if isinstance(converted, str):
                    markdown = converted.strip()
            except Exception:  # pragma: no cover - parser variability
                markdown = ""

    if not markdown:
        markdown = _strip_tags(SCRIPT_STYLE_PATTERN.sub(" ", html))

    if not markdown:
        return ""

    lines: list[str] = []
    for raw_line in markdown.replace("\r", "\n").splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if line:
            lines.append(line)
    cleaned = "\n".join(lines).strip()
    if not cleaned:
        return ""
    return cleaned if len(cleaned) <= max_chars else f"{cleaned[:max_chars].rstrip()}..."


def _extract_headings(html: str, *, max_headings: int = 40) -> tuple[str, ...]:
    headings: list[str] = []

    try:
        from bs4 import BeautifulSoup
    except ImportError:  # pragma: no cover - optional dependency
        BeautifulSoup = None

    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup.find_all(["h1", "h2", "h3"]):
            text = tag.get_text(" ", strip=True)
            if text and text not in headings:
                headings.append(text)
                if len(headings) >= max_headings:
                    break
        return tuple(headings)

    pattern = re.compile(r"<h[1-3][^>]*>(.*?)</h[1-3]>", flags=re.IGNORECASE | re.DOTALL)
    for raw in pattern.findall(html):
        text = _strip_tags(raw)
        if text and text not in headings:
            headings.append(text)
            if len(headings) >= max_headings:
                break
    return tuple(headings)


def _extract_code_blocks(html: str, *, max_blocks: int = 20, max_chars: int = 5000) -> tuple[str, ...]:
    blocks: list[str] = []

    try:
        from bs4 import BeautifulSoup
    except ImportError:  # pragma: no cover - optional dependency
        BeautifulSoup = None

    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "lxml")
        for node in soup.find_all(["pre", "code"]):
            text = node.get_text("\n", strip=True)
            if not text:
                continue
            cleaned = WHITESPACE_PATTERN.sub(" ", text).strip()
            if cleaned and cleaned not in blocks:
                if len(cleaned) > max_chars:
                    cleaned = f"{cleaned[:max_chars].rstrip()}..."
                blocks.append(cleaned)
                if len(blocks) >= max_blocks:
                    break
        return tuple(blocks)

    pattern = re.compile(r"<pre[^>]*>(.*?)</pre>|<code[^>]*>(.*?)</code>", flags=re.IGNORECASE | re.DOTALL)
    for raw_pre, raw_code in pattern.findall(html):
        raw = raw_pre or raw_code
        text = _strip_tags(raw)
        cleaned = WHITESPACE_PATTERN.sub(" ", text).strip()
        if cleaned and cleaned not in blocks:
            if len(cleaned) > max_chars:
                cleaned = f"{cleaned[:max_chars].rstrip()}..."
            blocks.append(cleaned)
            if len(blocks) >= max_blocks:
                break
    return tuple(blocks)
