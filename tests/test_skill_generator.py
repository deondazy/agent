import pytest

from denosysbot.skills.generator import SkillSynthesisError, build_skill_markdown
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


def test_build_skill_markdown_uses_model_assisted_synthesis_when_available() -> None:
    pages = [
        CrawledPage(
            url="https://filamentphp.com/docs/5.x/getting-started",
            title="Getting Started",
            excerpt="Install and configure Filament v5.",
            depth=0,
            markdown=(
                "# Getting Started\n"
                "Filament provides a panel builder for Laravel.\n"
                "composer require filament/filament:\"^5.0\"\n"
                "php artisan filament:install --panels\n"
            ),
            headings=("Getting Started", "Installation"),
            code_blocks=(
                'composer require filament/filament:"^5.0"',
                "php artisan filament:install --panels",
            ),
        ),
        CrawledPage(
            url="https://filamentphp.com/docs/5.x/resources/overview",
            title="Resources Overview",
            excerpt="Resources define CRUD interfaces for Eloquent models.",
            depth=1,
            markdown=(
                "# Resources\n"
                "Resources define CRUD interfaces for Eloquent models.\n"
                "php artisan make:filament-resource Customer --generate\n"
            ),
            headings=("Resources", "Overview"),
            code_blocks=("php artisan make:filament-resource Customer --generate",),
        ),
    ]

    prompts: list[str] = []

    def fake_model(prompt: str) -> str:
        prompts.append(prompt)
        return (
            "{"
            '"description":"FilamentPHP v5 admin panel workflows and resource patterns from official docs.",'
            '"triggers":["filament","panel-builder","resources"],'
            '"core_concepts":["Resources define CRUD interfaces for Eloquent models.","Panel providers configure panel paths and auth flows."],'
            '"installation_commands":["composer require filament/filament:\\"^5.0\\"","php artisan filament:install --panels"],'
            '"common_commands":["php artisan make:filament-user","php artisan make:filament-resource Customer --generate"],'
            '"best_practices":["Split resource schema and table configuration into dedicated files."],'
            '"pitfalls":["Avoid deprecated namespaces when upgrading to v5."],'
            '"page_highlights":[{"page":"Getting Started","url":"https://filamentphp.com/docs/5.x/getting-started","highlight":"Install Filament with composer and run panel install scaffolding."}]'
            "}"
        )

    skill_md = build_skill_markdown(
        skill_name="filament-v5",
        source_url="https://filamentphp.com/docs/5.x/getting-started",
        pages=pages,
        model_generate=fake_model,
    )

    assert len(prompts) == 1
    assert "## Best Practices" in skill_md
    assert "Split resource schema and table configuration into dedicated files." in skill_md
    assert "## Pitfalls & Notes" in skill_md
    assert "Avoid deprecated namespaces when upgrading to v5." in skill_md
    assert "php artisan make:filament-user" in skill_md


def test_build_skill_markdown_falls_back_when_model_payload_is_invalid() -> None:
    pages = [
        CrawledPage(
            url="https://example.com/docs/getting-started",
            title="Getting Started",
            excerpt="Install and configure the framework.",
            depth=0,
            markdown=(
                "Framework setup guide.\n"
                "composer require example/framework:\"^1.0\"\n"
                "php artisan example:install\n"
            ),
            headings=("Getting Started",),
            code_blocks=('composer require example/framework:"^1.0"', "php artisan example:install"),
        )
    ]

    skill_md = build_skill_markdown(
        skill_name="example-framework",
        source_url="https://example.com/docs/getting-started",
        pages=pages,
        model_generate=lambda _prompt: "not-json",
    )

    assert "## Core Concepts" in skill_md
    assert "composer require example/framework" in skill_md


def test_build_skill_markdown_require_model_raises_on_invalid_payload() -> None:
    pages = [
        CrawledPage(
            url="https://example.com/docs/getting-started",
            title="Getting Started",
            excerpt="Install and configure the framework.",
            depth=0,
            markdown="Framework setup guide.",
            headings=("Getting Started",),
            code_blocks=("php artisan example:install",),
        )
    ]

    with pytest.raises(SkillSynthesisError):
        build_skill_markdown(
            skill_name="example-framework",
            source_url="https://example.com/docs/getting-started",
            pages=pages,
            model_generate=lambda _prompt: "not-json",
            require_model=True,
        )


def test_build_skill_markdown_filters_noisy_documentation_pages() -> None:
    pages = [
        CrawledPage(
            url="https://filamentphp.com/docs/5.x/getting-started",
            title="Getting Started",
            excerpt="Start building a panel.",
            depth=0,
            markdown="Install with composer require filament/filament:\"^5.0\"",
            headings=("Getting Started",),
            code_blocks=('composer require filament/filament:"^5.0"',),
        ),
        CrawledPage(
            url="https://filamentphp.com/docs/5.x/introduction/help",
            title="Help",
            excerpt="Community support page.",
            depth=1,
            markdown="Help and support options.",
            headings=("Help",),
            code_blocks=(),
        ),
    ]

    skill_md = build_skill_markdown(
        skill_name="filament-v5",
        source_url="https://filamentphp.com/docs/5.x/getting-started",
        pages=pages,
    )

    assert "https://filamentphp.com/docs/5.x/getting-started" in skill_md
    assert "https://filamentphp.com/docs/5.x/introduction/help" not in skill_md


def test_build_skill_markdown_repairs_invalid_model_json_with_second_pass() -> None:
    pages = [
        CrawledPage(
            url="https://filamentphp.com/docs/5.x/getting-started",
            title="Getting Started",
            excerpt="Install and configure Filament v5 panel builder.",
            depth=0,
            markdown=(
                "Install Filament and scaffold an admin panel.\n"
                "composer require filament/filament:\"^5.0\"\n"
                "php artisan filament:install --panels\n"
            ),
            headings=("Getting Started", "Installation"),
            code_blocks=(
                'composer require filament/filament:"^5.0"',
                "php artisan filament:install --panels",
            ),
        ),
        CrawledPage(
            url="https://filamentphp.com/docs/5.x/resources/overview",
            title="Resources Overview",
            excerpt="Resources define CRUD interfaces for models.",
            depth=1,
            markdown="Resources define CRUD interfaces and pages.",
            headings=("Resources",),
            code_blocks=("php artisan make:filament-resource Customer --generate",),
        ),
    ]

    calls = {"count": 0}

    def flaky_model(_prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return "Here is your JSON: {invalid"
        return (
            "{"
            '"description":"Filament v5 setup and CRUD workflow guidance from official docs.",'
            '"triggers":["filament","resources"],'
            '"core_concepts":["Filament v5 uses panel providers for admin configuration.","Resources define CRUD interfaces for Eloquent models.","Tables and forms are schema-driven for record management.","Actions provide modal-based workflow operations."],'
            '"installation_commands":["composer require filament/filament:\\"^5.0\\"","php artisan filament:install --panels"],'
            '"common_commands":["php artisan make:filament-user","php artisan make:filament-resource Customer --generate"],'
            '"resources":["Resources define CRUD interfaces for Eloquent models.","Use generators to scaffold resource pages."],'
            '"forms":["Build form schemas with reusable field components.","Keep validation close to schema field declarations."],'
            '"tables":["Use sortable and searchable columns for list pages.","Add filters and actions for operational workflows."],'
            '"actions":["Use actions for record-level workflows.","Require confirmation for destructive actions."],'
            '"panel_configuration":["Configure panel path and auth in panel providers.","Discover resources and pages automatically."],'
            '"testing":["Use Livewire tests for create and edit flows."],'
            '"upgrade_notes":["Review namespace changes when migrating to v5."],'
            '"best_practices":["Split schema and table logic into dedicated files."],'
            '"pitfalls":["Avoid mixing deprecated namespaces with v5 imports."],'
            '"page_highlights":[{"page":"Getting Started","url":"https://filamentphp.com/docs/5.x/getting-started","highlight":"Install Filament with composer and run panel installation commands to bootstrap the admin panel."}]'
            "}"
        )

    skill_md = build_skill_markdown(
        skill_name="filament-v5",
        source_url="https://filamentphp.com/docs/5.x/getting-started",
        pages=pages,
        model_generate=flaky_model,
        require_model=True,
    )

    assert calls["count"] == 2
    assert "## Resources" in skill_md
    assert "composer require filament/filament" in skill_md
