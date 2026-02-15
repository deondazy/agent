from denosysbot.tools.web import extract_urls, normalize_duckduckgo_result_url, parse_duckduckgo_results


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
