import httpx

import denosysbot.tools.web as web_module
from denosysbot.tools.web import (
    crawl_docs_site,
    extract_urls,
    normalize_duckduckgo_result_url,
    parse_duckduckgo_results,
)


def test_normalize_duckduckgo_redirect_url_extracts_target() -> None:
    redirected = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fguide"
    normalized = normalize_duckduckgo_result_url(redirected)

    assert normalized == "https://example.com/guide"


def test_parse_duckduckgo_results_extracts_title_and_url() -> None:
    html = (
        '<a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdocs">'
        "Example Docs"
        "</a>"
        '<a class="result__a" href="https://example.org/blog">Blog Post</a>'
    )

    parsed = parse_duckduckgo_results(html)

    assert len(parsed) == 2
    assert parsed[0].title == "Example Docs"
    assert parsed[0].url == "https://example.com/docs"
    assert parsed[1].title == "Blog Post"
    assert parsed[1].url == "https://example.org/blog"


def test_extract_urls_returns_http_and_https_links() -> None:
    text = "Go to https://filamentphp.com/docs/5.x/getting-started and also http://example.org/page."

    urls = extract_urls(text)

    assert urls == (
        "https://filamentphp.com/docs/5.x/getting-started",
        "http://example.org/page",
    )


def test_crawl_docs_site_follows_internal_doc_links_page_by_page() -> None:
    start = "https://filamentphp.com/docs/5.x/getting-started"
    pages = {
        "https://filamentphp.com/docs/5.x/getting-started": (
            "<html><head><title>Getting Started</title></head><body>"
            '<a href="/docs/5.x/panels/installation">Panels</a>'
            '<a href="/docs/5.x/forms/overview">Forms</a>'
            '<a href="/docs/4.x/legacy">Legacy</a>'
            "</body></html>"
        ),
        "https://filamentphp.com/docs/5.x/panels/installation": (
            "<html><head><title>Panels Installation</title></head><body>Install panels</body></html>"
        ),
        "https://filamentphp.com/docs/5.x/forms/overview": (
            "<html><head><title>Forms Overview</title></head><body>Build forms</body></html>"
        ),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = pages.get(str(request.url))
        if body is None:
            return httpx.Response(404, text="not found")
        return httpx.Response(200, text=body, headers={"content-type": "text/html; charset=utf-8"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    crawled = crawl_docs_site(start, max_pages=10, max_depth=2, http_client=client)
    urls = [page.url for page in crawled]

    assert "https://filamentphp.com/docs/5.x/getting-started" in urls
    assert "https://filamentphp.com/docs/5.x/panels/installation" in urls
    assert "https://filamentphp.com/docs/5.x/forms/overview" in urls
    assert "https://filamentphp.com/docs/4.x/legacy" not in urls


def test_crawl_docs_site_uses_playwright_when_http_fetch_fails(monkeypatch) -> None:
    start = "https://filamentphp.com/docs/5.x/getting-started"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns failure", request=request)

    monkeypatch.setattr(
        web_module,
        "_render_with_playwright",
        lambda _url: (
            "<html><head><title>Rendered page</title></head>"
            "<body><h1>Getting Started</h1><p>Rendered via browser fallback.</p></body></html>"
        ),
        raising=True,
    )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    crawled = crawl_docs_site(start, max_pages=5, max_depth=1, http_client=client)

    assert len(crawled) == 1
    assert crawled[0].title == "Rendered page"
    assert crawled[0].url == start


def test_crawl_docs_site_accepts_html_body_with_non_html_content_type() -> None:
    start = "https://filamentphp.com/docs/5.x/getting-started"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "<html><head><title>Getting Started</title></head>"
                "<body><h1>Intro</h1><p>Docs page body.</p></body></html>"
            ),
            headers={"content-type": "text/plain"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    crawled = crawl_docs_site(start, max_pages=5, max_depth=1, http_client=client)

    assert len(crawled) == 1
    assert crawled[0].title == "Getting Started"
