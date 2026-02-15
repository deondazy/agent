from denosysbot.skills.generator import build_skill_markdown
from denosysbot.tools.web import CrawledPage


def test_build_skill_markdown_generates_structured_sections_and_commands() -> None:
    pages = [
        CrawledPage(
            url="https://filamentphp.com/docs/5.x/getting-started",
            title="Getting Started",
            excerpt="Filament is a server-driven UI framework for Laravel.",
            depth=0,
            markdown=(
                "Filament is a server-driven UI framework for Laravel.\n\n"
                "Install with composer require filament/filament:\"^5.0\".\n"
            ),
            headings=("Getting Started", "Installation"),
            code_blocks=('composer require filament/filament:"^5.0"', "php artisan filament:install --panels"),
        ),
        CrawledPage(
            url="https://filamentphp.com/docs/5.x/resources/overview",
            title="Resources Overview",
            excerpt="Resources provide CRUD interfaces.",
            depth=1,
            markdown="Resources provide CRUD interfaces for Eloquent models.",
            headings=("Resources Overview",),
            code_blocks=("php artisan make:filament-resource Customer --generate",),
        ),
    ]

    skill_md = build_skill_markdown(
        skill_name="filament-v5",
        source_url="https://filamentphp.com/docs/5.x/getting-started",
        pages=pages,
    )

    assert skill_md.startswith("---\n")
    assert "## Documentation" in skill_md
    assert "## Installation & Setup" in skill_md
    assert "## Core Concepts" in skill_md
    assert "composer require filament/filament" in skill_md
    assert "php artisan make:filament-resource" in skill_md


def test_build_skill_markdown_filters_duplicate_and_partial_commands() -> None:
    pages = [
        CrawledPage(
            url="https://example.com/docs/getting-started",
            title="Getting Started",
            excerpt="Install and scaffold the app.",
            depth=0,
            markdown=(
                "Install package\n"
                "composer require package/core:\"^1.0\"\n"
                "composer require package/core:\"~1.0\"\n"
                "composer config repositories.private\n"
                "php artisan package:install\n"
            ),
            headings=("Installation",),
            code_blocks=(
                'composer require package/core:"^1.0"',
                'composer require package/core:"~1.0"',
                "composer config repositories.private",
                "php artisan package:install",
            ),
        )
    ]

    skill_md = build_skill_markdown(
        skill_name="package-docs",
        source_url="https://example.com/docs/getting-started",
        pages=pages,
    )

    assert skill_md.count("composer require package/core") == 1
    assert "composer config repositories.private" not in skill_md
    assert "php artisan package:install" in skill_md


def test_build_skill_markdown_adds_page_highlights_from_page_content() -> None:
    pages = [
        CrawledPage(
            url="https://example.com/docs/resources",
            title="Resources",
            excerpt="Resources generate CRUD pages for Eloquent models.",
            depth=1,
            markdown=(
                "# Resources\n"
                "Resources generate CRUD pages for Eloquent models.\n"
                "Use generators to scaffold list, create, edit, and view pages.\n"
                "php artisan make:resource Post\n"
            ),
            headings=("Resources", "Scaffolding"),
            code_blocks=("php artisan make:resource Post",),
        )
    ]

    skill_md = build_skill_markdown(
        skill_name="example-framework",
        source_url="https://example.com/docs/getting-started",
        pages=pages,
    )

    assert "## Page Highlights" in skill_md
    assert "Resources generate CRUD pages for Eloquent models" in skill_md
