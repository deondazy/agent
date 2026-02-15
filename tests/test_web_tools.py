from denosysbot.tools.web import normalize_duckduckgo_result_url, parse_duckduckgo_results


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
