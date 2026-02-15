from collections import deque
import inspect
import json
from pathlib import Path
import re
import time
from types import SimpleNamespace

from denosysbot.adapters.models.base import ProviderError
from denosysbot.skills.generator import SkillSynthesisError
from denosysbot.cli import PROGRESS_PHRASES, build_chat_prompt, main, run_tui

ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(value: str) -> str:
    return ANSI_PATTERN.sub("", value)


class FakeGateway:
    def __init__(self, responses: list[str] | None = None, raise_error: bool = False):
        self.responses = deque(responses or [])
        self.raise_error = raise_error
        self.prompts: list[str] = []

    def generate(self, prompt: str, **kwargs: str) -> str:
        self.prompts.append(prompt)
        if self.raise_error:
            raise ProviderError("provider boom")
        if self.responses:
            return self.responses.popleft()
        return "default-response"


class SlowGateway(FakeGateway):
    def __init__(self, *, delay_seconds: float, responses: list[str] | None = None):
        super().__init__(responses=responses)
        self.delay_seconds = delay_seconds

    def generate(self, prompt: str, **kwargs: str) -> str:
        self.prompts.append(prompt)
        time.sleep(self.delay_seconds)
        if self.responses:
            return self.responses.popleft()
        return "default-response"


def test_main_tui_invokes_interactive_mode(monkeypatch) -> None:
    called = {"ran": False}

    def _fake_run_tui(**kwargs):
        called["ran"] = True
        return 0

    monkeypatch.setattr("denosysbot.cli.run_tui", _fake_run_tui)

    code = main(["tui"])

    assert code == 0
    assert called["ran"] is True


def test_main_config_invokes_walkthrough_with_default_env(monkeypatch) -> None:
    called = {"path": None}

    def _fake_run_walkthrough(env_path: Path) -> None:
        called["path"] = env_path

    monkeypatch.setattr("denosysbot.cli.run_walkthrough", _fake_run_walkthrough)

    code = main(["config"])

    assert code == 0
    assert called["path"] == Path(".env")


def test_main_config_invokes_walkthrough_with_custom_env(monkeypatch) -> None:
    called = {"path": None}

    def _fake_run_walkthrough(env_path: Path) -> None:
        called["path"] = env_path

    monkeypatch.setattr("denosysbot.cli.run_walkthrough", _fake_run_walkthrough)

    code = main(["config", "--env-file", "config/local.env"])

    assert code == 0
    assert called["path"] == Path("config/local.env")


def test_main_without_subcommand_shows_help(capsys) -> None:
    code = main([])

    captured = capsys.readouterr()

    assert code == 1
    assert "usage:" in captured.out


def test_run_tui_generates_response_and_exits(tmp_path: Path) -> None:
    inputs = iter(["hello", "/exit"])
    outputs: list[str] = []
    prompts: list[str] = []
    gateway = FakeGateway(responses=["hi there"])
    history_path = tmp_path / "history.json"

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(inputs)

    code = run_tui(
        gateway=gateway,
        input_fn=fake_input,
        output_fn=outputs.append,
        history_path=history_path,
    )

    assert code == 0
    assert any("DenoSysBot TUI" in line for line in outputs)
    assert any("terminal AI assistant" in line for line in outputs)
    assert any("Commands: /help, /reset, /exit" in line for line in outputs)
    assert any(line.startswith("denosysbot> thinking") for line in outputs)
    normalized_outputs = [strip_ansi(line) for line in outputs]
    assert "DenoSysBot" in normalized_outputs
    assert "hi there" in normalized_outputs
    assert normalized_outputs.index("DenoSysBot") < normalized_outputs.index("hi there")
    assert normalized_outputs.index("hi there") == normalized_outputs.index("DenoSysBot") + 1
    first_progress_index = next(
        idx for idx, line in enumerate(outputs) if line.startswith("denosysbot> thinking")
    )
    assert first_progress_index < normalized_outputs.index("DenoSysBot")
    assert prompts[0] == ""
    assert len(gateway.prompts) == 1


def test_run_tui_handles_provider_error_and_continues(tmp_path: Path) -> None:
    inputs = iter(["hello", "/exit"])
    outputs: list[str] = []
    gateway = FakeGateway(raise_error=True)
    history_path = tmp_path / "history.json"

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    assert code == 0
    assert any("error:" in line for line in outputs)


def test_run_tui_persists_user_turn_even_when_provider_errors(tmp_path: Path) -> None:
    inputs = iter(["hello", "/exit"])
    outputs: list[str] = []
    gateway = FakeGateway(raise_error=True)
    history_path = tmp_path / "history.json"

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    assert code == 0
    assert any("error:" in line for line in outputs)
    assert json.loads(history_path.read_text()) == [
        {"role": "user", "content": "hello"},
    ]


def test_run_tui_progress_phrase_changes_between_submissions(tmp_path: Path) -> None:
    inputs = iter(["hello", "again", "/exit"])
    outputs: list[str] = []
    gateway = FakeGateway(responses=["first reply", "second reply"])
    history_path = tmp_path / "history.json"

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    progress_lines = [
        line
        for line in outputs
        if line.startswith("denosysbot> ")
        and line not in {"denosysbot> first reply", "denosysbot> second reply"}
        and "error:" not in line
    ]

    assert code == 0
    assert len(progress_lines) == 2
    assert progress_lines[0] != progress_lines[1]


def test_run_tui_animates_ellipsis_while_waiting_for_response(tmp_path: Path) -> None:
    inputs = iter(["hello", "/exit"])
    outputs: list[str] = []
    gateway = SlowGateway(delay_seconds=0.06, responses=["hi"])
    history_path = tmp_path / "history.json"

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        progress_interval_seconds=0.01,
        progress_phrase_interval_seconds=0.25,
        history_path=history_path,
    )

    progress_lines = [
        line
        for line in outputs
        if line.startswith("denosysbot> ")
        and line != "denosysbot> hi"
        and "error:" not in line
    ]
    payloads = [line.removeprefix("denosysbot> ") for line in progress_lines]
    phrases = [payload.rstrip(".") for payload in payloads]
    ellipsis_suffixes = [payload[len(payload.rstrip(".")) :] for payload in payloads]

    assert code == 0
    assert len(progress_lines) >= 2
    assert len(set(phrases)) == 1
    assert len(set(ellipsis_suffixes)) >= 2


def test_progress_phrase_pool_is_large() -> None:
    assert len(PROGRESS_PHRASES) >= 16


def test_run_tui_default_phrase_interval_is_slow() -> None:
    signature = inspect.signature(run_tui)
    default_interval = signature.parameters["progress_phrase_interval_seconds"].default
    assert default_interval >= 3.0


def test_build_chat_prompt_keeps_older_context_when_history_is_long() -> None:
    history: list[tuple[str, str]] = [
        ("user", "I am building a fintech app called BiyaLink."),
        ("assistant", "Noted."),
    ]
    for idx in range(6):
        history.append(("user", f"filler-user-{idx}"))
        history.append(("assistant", f"filler-assistant-{idx}"))

    prompt = build_chat_prompt(history, "Do you remember BiyaLink?")

    assert "user: I am building a fintech app called BiyaLink." in prompt


def test_build_chat_prompt_includes_runtime_local_time_context() -> None:
    prompt = build_chat_prompt([], "What is my local time?")

    assert "Current local date/time:" in prompt
    assert "Never guess date/time values." in prompt


def test_run_tui_loads_persisted_history_into_prompt(tmp_path: Path) -> None:
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps(
            [
                {"role": "user", "content": "previous question"},
                {"role": "assistant", "content": "previous answer"},
            ]
        )
    )
    inputs = iter(["new question", "/exit"])
    gateway = FakeGateway(responses=["new answer"])
    outputs: list[str] = []

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    assert code == 0
    assert len(gateway.prompts) == 1
    prompt = gateway.prompts[0]
    assert "user: previous question" in prompt
    assert "assistant: previous answer" in prompt
    assert "user: new question" in prompt


def test_run_tui_persists_history_after_response(tmp_path: Path) -> None:
    history_path = tmp_path / "history.json"
    inputs = iter(["hello", "/exit"])
    gateway = FakeGateway(responses=["hi there"])
    outputs: list[str] = []

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    assert code == 0
    persisted = json.loads(history_path.read_text())
    assert persisted == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]


def test_run_tui_reset_clears_persisted_history(tmp_path: Path) -> None:
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps(
            [
                {"role": "user", "content": "stale question"},
                {"role": "assistant", "content": "stale answer"},
            ]
        )
    )
    inputs = iter(["/reset", "/exit"])
    gateway = FakeGateway(responses=["unused"])
    outputs: list[str] = []

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    assert code == 0
    assert "Conversation reset." in outputs
    assert json.loads(history_path.read_text()) == []


def test_run_tui_skill_create_command_writes_skill_file(tmp_path: Path, monkeypatch) -> None:
    inputs = iter(
        [
            "/skill create deploy-docker | Deploy apps with docker compose | docker,compose,deploy",
            "/exit",
        ]
    )
    outputs: list[str] = []
    gateway = FakeGateway(responses=["unused"])
    history_path = tmp_path / "history.json"
    skills_dir = tmp_path / "skills"
    monkeypatch.setenv("DENOSYSBOT_SKILLS_DIR", str(skills_dir))

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    created = skills_dir / "deploy-docker.md"
    assert code == 0
    assert created.exists() is True
    skill_markdown = created.read_text()
    assert "name: deploy-docker" in skill_markdown
    assert "description: Deploy apps with docker compose" in skill_markdown
    assert "triggers: docker,compose,deploy" in skill_markdown
    assert any("Created skill:" in line for line in outputs)
    assert gateway.prompts == []


def test_run_tui_includes_relevant_skill_context_in_prompt(tmp_path: Path, monkeypatch) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "deploy-docker.md").write_text(
        (
            "---\n"
            "name: deploy-docker\n"
            "description: Docker deployment workflows\n"
            "triggers: docker,compose,deploy\n"
            "---\n\n"
            "Use Docker Compose for local and production deployments.\n"
        )
    )
    monkeypatch.setenv("DENOSYSBOT_SKILLS_DIR", str(skills_dir))

    inputs = iter(["How do I deploy this using docker compose?", "/exit"])
    outputs: list[str] = []
    gateway = FakeGateway(responses=["Use docker compose up -d"])
    history_path = tmp_path / "history.json"

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    assert code == 0
    assert len(gateway.prompts) == 1
    prompt = gateway.prompts[0]
    assert "Relevant local skills:" in prompt
    assert "deploy-docker" in prompt
    assert "Docker deployment workflows" in prompt


def test_run_tui_web_command_prints_results_without_calling_model(
    tmp_path: Path, monkeypatch
) -> None:
    import denosysbot.cli as cli_module

    monkeypatch.setattr(
        cli_module,
        "build_web_context",
        lambda query, max_results=3: (
            f"Live web results for: {query}",
            [SimpleNamespace(title="Example", url="https://example.com")],
        ),
        raising=False,
    )

    inputs = iter(["/web denosysbot", "/exit"])
    outputs: list[str] = []
    gateway = FakeGateway(responses=["unused"])
    history_path = tmp_path / "history.json"

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    assert code == 0
    assert any(line.startswith("Web results:") for line in outputs)
    assert any("https://example.com" in line for line in outputs)
    assert gateway.prompts == []


def test_run_tui_skill_learn_creates_markdown_from_web_context(
    tmp_path: Path, monkeypatch
) -> None:
    import denosysbot.cli as cli_module

    monkeypatch.setattr(
        cli_module,
        "build_web_context",
        lambda query, max_results=3: (
            f"Live web results for: {query}\n1. Example - https://example.com",
            [SimpleNamespace(title="Example", url="https://example.com", excerpt="reference")],
        ),
        raising=False,
    )

    skills_dir = tmp_path / "skills"
    monkeypatch.setenv("DENOSYSBOT_SKILLS_DIR", str(skills_dir))

    inputs = iter(["/skill learn docker-guide | docker compose deployment", "/exit"])
    outputs: list[str] = []
    gateway = FakeGateway(responses=["unused"])
    history_path = tmp_path / "history.json"

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    created = skills_dir / "docker-guide.md"
    assert code == 0
    assert created.exists() is True
    markdown = created.read_text()
    assert "name: docker-guide" in markdown
    assert "Learned guidance for docker compose deployment" in markdown
    assert "## Learned References" in markdown
    assert "https://example.com" in markdown
    assert any("Learned from 1 web result(s)." in line for line in outputs)
    assert gateway.prompts == []


def test_run_tui_skill_edit_updates_existing_skill(tmp_path: Path, monkeypatch) -> None:
    skills_dir = tmp_path / "skills"
    monkeypatch.setenv("DENOSYSBOT_SKILLS_DIR", str(skills_dir))

    inputs = iter(
        [
            "/skill create deploy-docker | Deploy apps with docker compose | docker,compose,deploy",
            "/skill edit deploy-docker | Deploy apps with kubernetes | kubernetes,helm,deploy",
            "/exit",
        ]
    )
    outputs: list[str] = []
    gateway = FakeGateway(responses=["unused"])
    history_path = tmp_path / "history.json"

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    created = skills_dir / "deploy-docker.md"
    assert code == 0
    assert created.exists() is True
    text = created.read_text()
    assert "description: Deploy apps with kubernetes" in text
    assert "triggers: kubernetes,helm,deploy" in text
    assert any("Updated skill:" in line for line in outputs)
    assert gateway.prompts == []


def test_run_tui_natural_language_url_skill_request_creates_skill(
    tmp_path: Path, monkeypatch
) -> None:
    import denosysbot.cli as cli_module

    monkeypatch.setattr(
        cli_module,
        "crawl_docs_site",
        lambda start_url, max_pages=16, max_depth=2, http_client=None: [
            SimpleNamespace(
                url="https://filamentphp.com/docs/5.x/getting-started",
                title="Getting Started",
                excerpt="Filament v5 documentation excerpt",
                depth=0,
            ),
            SimpleNamespace(
                url="https://filamentphp.com/docs/5.x/panels/installation",
                title="Panels Installation",
                excerpt="Install and configure panels.",
                depth=1,
            ),
        ],
        raising=False,
    )
    monkeypatch.setattr(
        cli_module,
        "build_crawl_context",
        lambda pages: (
            "Crawled documentation pages:\n"
            "1. https://filamentphp.com/docs/5.x/getting-started\n"
            "   Excerpt: Filament v5 documentation excerpt\n"
            "2. https://filamentphp.com/docs/5.x/panels/installation",
            pages,
        ),
        raising=False,
    )

    skills_dir = tmp_path / "skills"
    monkeypatch.setenv("DENOSYSBOT_SKILLS_DIR", str(skills_dir))

    inputs = iter(
        [
            "Go to https://filamentphp.com/docs/5.x/getting-started learn everything about filament v5 and create a skill for it",
            "/exit",
        ]
    )
    outputs: list[str] = []
    gateway = FakeGateway(
        responses=[
            (
                "{"
                '"description":"Filament v5 docs synthesis.",'
                '"triggers":["filament","resources"],'
                '"core_concepts":["Filament v5 provides admin panel scaffolding.","Resources map Eloquent models to CRUD workflows.","Panel providers configure authentication and navigation.","Tables and forms drive resource UX."],'
                '"installation_commands":["composer require filament/filament:\\"^5.0\\"","php artisan filament:install --panels"],'
                '"common_commands":["php artisan make:filament-user","php artisan make:filament-resource Customer --generate"],'
                '"resources":["Resources are static classes for CRUD interfaces.","Generate resources with artisan commands."],'
                '"forms":["Build form schemas with field components.","Use validation rules directly in schema definitions."],'
                '"tables":["Use sortable/searchable columns.","Apply filters and bulk actions to tables."],'
                '"actions":["Use actions for modal-based operations.","Require confirmation for destructive actions."],'
                '"panel_configuration":["Set panel path and auth in panel provider.","Discover resources and pages automatically."],'
                '"testing":["Test resource flows with Livewire/Pest."],'
                '"upgrade_notes":["Check deprecated namespaces during upgrades."],'
                '"best_practices":["Split schemas and tables into separate classes."],'
                '"pitfalls":["Avoid mixed v4 and v5 namespace imports."],'
                '"page_highlights":[{"page":"Getting Started","url":"https://filamentphp.com/docs/5.x/getting-started","highlight":"Filament installation starts with composer require and panel setup commands."}]'
                "}"
            )
        ]
    )
    history_path = tmp_path / "history.json"

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    created_files = list(skills_dir.glob("**/SKILL.md"))
    assert code == 0
    assert len(created_files) == 1
    skill_text = created_files[0].read_text()
    assert "## Documentation" in skill_text
    assert "## Core Concepts" in skill_text
    assert "https://filamentphp.com/docs/5.x/getting-started" in skill_text
    assert any("Created skill:" in line for line in outputs)
    assert len(gateway.prompts) == 1


def test_run_tui_natural_language_url_skill_request_uses_model_synthesis(
    tmp_path: Path, monkeypatch
) -> None:
    import denosysbot.cli as cli_module

    pages = [
        SimpleNamespace(
            url="https://filamentphp.com/docs/5.x/getting-started",
            title="Getting Started",
            excerpt="Filament setup and installation.",
            depth=0,
            markdown=(
                "# Getting Started\n"
                "Filament provides an admin panel builder.\n"
                "composer require filament/filament:\"^5.0\"\n"
                "php artisan filament:install --panels\n"
            ),
            headings=("Getting Started", "Installation"),
            code_blocks=(
                'composer require filament/filament:"^5.0"',
                "php artisan filament:install --panels",
            ),
        ),
        SimpleNamespace(
            url="https://filamentphp.com/docs/5.x/resources/overview",
            title="Resources Overview",
            excerpt="Resources are static CRUD definitions.",
            depth=1,
            markdown=(
                "# Resources\n"
                "Resources are static classes used to build CRUD interfaces.\n"
                "php artisan make:filament-resource Customer --generate\n"
            ),
            headings=("Resources", "Overview"),
            code_blocks=("php artisan make:filament-resource Customer --generate",),
        ),
    ]

    monkeypatch.setattr(
        cli_module,
        "crawl_docs_site",
        lambda start_url, max_pages=16, max_depth=2, http_client=None: pages,
        raising=False,
    )
    monkeypatch.setattr(
        cli_module,
        "build_crawl_context",
        lambda crawled: ("Crawled context", crawled),
        raising=False,
    )

    skills_dir = tmp_path / "skills"
    monkeypatch.setenv("DENOSYSBOT_SKILLS_DIR", str(skills_dir))

    model_response = (
        "{"
        '"description":"FilamentPHP v5 setup, resources, and table workflows from official docs.",'
        '"triggers":["filament","resources","tables"],'
        '"core_concepts":["Resources define CRUD interfaces for Eloquent models.","Panel providers register auth and navigation.","Filament tables support sorting, searching, filters, and actions.","Filament forms define schema-driven validation and input rendering."],'
        '"installation_commands":["composer require filament/filament:\\"^5.0\\"","php artisan filament:install --panels"],'
        '"common_commands":["php artisan make:filament-user","php artisan make:filament-resource Customer --generate"],'
        '"resources":["Resources define CRUD interfaces for Eloquent models.","Use --generate to scaffold resources from schema."],'
        '"forms":["Define form schemas with reusable components.","Use validation methods directly on fields."],'
        '"tables":["Define table columns and filters for list pages.","Use actions and bulk actions for workflows."],'
        '"actions":["Use actions to run record-level workflows.","Require confirmation for destructive actions."],'
        '"panel_configuration":["Configure panel path and auth in provider.","Discover resources and pages automatically."],'
        '"testing":["Use Livewire tests for create/edit flows."],'
        '"upgrade_notes":["Review namespace changes when upgrading to v5."],'
        '"best_practices":["Use generated resources and split schema/table configuration for maintainability."],'
        '"pitfalls":["Check namespace changes when migrating older Filament projects."],'
        '"page_highlights":[{"page":"Resources Overview","url":"https://filamentphp.com/docs/5.x/resources/overview","highlight":"Resources are static classes used to build CRUD interfaces."}]'
        "}"
    )

    inputs = iter(
        [
            "Go to https://filamentphp.com/docs/5.x/getting-started learn everything about filament v5 and create a skill for it",
            "/exit",
        ]
    )
    outputs: list[str] = []
    gateway = FakeGateway(responses=[model_response])
    history_path = tmp_path / "history.json"

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    created_files = list(skills_dir.glob("**/SKILL.md"))
    assert code == 0
    assert len(created_files) == 1
    skill_text = created_files[0].read_text()
    assert "## Best Practices" in skill_text
    assert "## Pitfalls & Notes" in skill_text
    assert "php artisan make:filament-user" in skill_text
    assert len(gateway.prompts) == 1


def test_run_tui_natural_language_url_skill_request_reports_crawl_failure(
    tmp_path: Path, monkeypatch
) -> None:
    import denosysbot.cli as cli_module

    monkeypatch.setattr(
        cli_module,
        "crawl_docs_site",
        lambda start_url, max_pages=16, max_depth=2, http_client=None: [],
        raising=False,
    )
    monkeypatch.setattr(
        cli_module,
        "build_crawl_context",
        lambda pages: ("", pages),
        raising=False,
    )

    skills_dir = tmp_path / "skills"
    monkeypatch.setenv("DENOSYSBOT_SKILLS_DIR", str(skills_dir))

    inputs = iter(
        [
            "Go to https://filamentphp.com/docs/5.x/getting-started learn everything about filament v5 and create a skill for it",
            "/exit",
        ]
    )
    outputs: list[str] = []
    gateway = FakeGateway(responses=["unused"])
    history_path = tmp_path / "history.json"

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    assert code == 0
    assert any("failed to crawl documentation pages" in line for line in outputs)


def test_run_tui_natural_language_url_skill_request_shows_progress_updates(
    tmp_path: Path, monkeypatch
) -> None:
    import denosysbot.cli as cli_module

    pages = [
        SimpleNamespace(
            url="https://filamentphp.com/docs/5.x/getting-started",
            title="Getting Started",
            excerpt="Filament setup.",
            depth=0,
            markdown="composer require filament/filament:\"^5.0\"",
            headings=("Getting Started",),
            code_blocks=('composer require filament/filament:"^5.0"',),
        )
    ]

    def slow_crawl(start_url, max_pages=16, max_depth=2, http_client=None):
        time.sleep(0.06)
        return pages

    monkeypatch.setattr(cli_module, "crawl_docs_site", slow_crawl, raising=False)
    monkeypatch.setattr(cli_module, "build_crawl_context", lambda crawled: ("Crawled context", crawled), raising=False)
    monkeypatch.setattr(
        cli_module,
        "build_skill_draft",
        lambda **kwargs: SimpleNamespace(
            name="filament-v5",
            description="Filament skill",
            triggers=("filament", "v5"),
            body="# FilamentPHP v5\n\n## Documentation\n- https://filamentphp.com/docs/5.x/getting-started\n",
        ),
        raising=False,
    )

    skills_dir = tmp_path / "skills"
    monkeypatch.setenv("DENOSYSBOT_SKILLS_DIR", str(skills_dir))

    inputs = iter(
        [
            "Go to https://filamentphp.com/docs/5.x/getting-started learn everything about filament v5 and create a skill for it",
            "/exit",
        ]
    )
    outputs: list[str] = []
    gateway = FakeGateway(responses=["unused"])
    history_path = tmp_path / "history.json"

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        progress_interval_seconds=0.01,
        progress_phrase_interval_seconds=0.20,
        history_path=history_path,
    )

    progress_lines = [line for line in outputs if line.startswith("denosysbot> ")]
    assert code == 0
    assert any("Created skill:" in line for line in outputs)
    assert any("thinking" in line or "working through it" in line for line in progress_lines)


def test_run_tui_natural_language_url_skill_request_reports_synthesis_error(
    tmp_path: Path, monkeypatch
) -> None:
    import denosysbot.cli as cli_module

    pages = [
        SimpleNamespace(
            url="https://filamentphp.com/docs/5.x/getting-started",
            title="Getting Started",
            excerpt="Filament setup.",
            depth=0,
            markdown="Install docs",
            headings=("Getting Started",),
            code_blocks=(),
        )
    ]
    monkeypatch.setattr(cli_module, "crawl_docs_site", lambda *args, **kwargs: pages, raising=False)
    monkeypatch.setattr(cli_module, "build_crawl_context", lambda crawled: ("Crawled context", crawled), raising=False)
    monkeypatch.setattr(
        cli_module,
        "build_skill_draft",
        lambda **kwargs: (_ for _ in ()).throw(SkillSynthesisError("quality gate failed")),
        raising=False,
    )

    skills_dir = tmp_path / "skills"
    monkeypatch.setenv("DENOSYSBOT_SKILLS_DIR", str(skills_dir))

    inputs = iter(
        [
            "Go to https://filamentphp.com/docs/5.x/getting-started learn everything about filament v5 and create a skill for it",
            "/exit",
        ]
    )
    outputs: list[str] = []
    gateway = FakeGateway(responses=["unused"])
    history_path = tmp_path / "history.json"

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
        history_path=history_path,
    )

    assert code == 0
    assert any("skill synthesis error:" in line for line in outputs)
