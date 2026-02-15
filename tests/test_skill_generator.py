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
