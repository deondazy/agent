from collections import deque
from pathlib import Path

from denosysbot.cli import main, run_tui


class FakeGateway:
    def __init__(self, responses: list[str] | None = None):
        self.responses = deque(responses or [])
        self.prompts: list[str] = []

    def generate(self, prompt: str, **kwargs: str) -> str:
        self.prompts.append(prompt)
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


def test_run_tui_launches_textual_app_with_gateway() -> None:
    launched: dict[str, object] = {}
    gateway = FakeGateway(responses=["hi there"])

    class FakeTextualApp:
        def __init__(self, *, gateway):
            launched["gateway"] = gateway

        def run(self) -> None:
            launched["ran"] = True

    code = run_tui(
        gateway=gateway,
        app_cls=FakeTextualApp,
    )

    assert code == 0
    assert launched["gateway"] is gateway
    assert launched["ran"] is True
