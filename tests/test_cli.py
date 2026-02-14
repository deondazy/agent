from collections import deque

from denosysbot.adapters.models.base import ProviderError
from denosysbot.cli import main, run_tui


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


def test_main_tui_invokes_interactive_mode(monkeypatch) -> None:
    called = {"ran": False}

    def _fake_run_tui(**kwargs):
        called["ran"] = True
        return 0

    monkeypatch.setattr("denosysbot.cli.run_tui", _fake_run_tui)

    code = main(["tui"])

    assert code == 0
    assert called["ran"] is True


def test_main_without_subcommand_shows_help(capsys) -> None:
    code = main([])

    captured = capsys.readouterr()

    assert code == 1
    assert "usage:" in captured.out


def test_run_tui_generates_response_and_exits() -> None:
    inputs = iter(["hello", "/exit"])
    outputs: list[str] = []
    prompts: list[str] = []
    gateway = FakeGateway(responses=["hi there"])

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(inputs)

    code = run_tui(
        gateway=gateway,
        input_fn=fake_input,
        output_fn=outputs.append,
    )

    assert code == 0
    assert any("DenoSysBot TUI" in line for line in outputs)
    assert any("terminal AI assistant" in line for line in outputs)
    assert any("Commands: /help, /reset, /exit" in line for line in outputs)
    assert any("denosysbot> hi there" in line for line in outputs)
    assert prompts[0] == "> "
    assert len(gateway.prompts) == 1


def test_run_tui_handles_provider_error_and_continues() -> None:
    inputs = iter(["hello", "/exit"])
    outputs: list[str] = []
    gateway = FakeGateway(raise_error=True)

    code = run_tui(
        gateway=gateway,
        input_fn=lambda _prompt: next(inputs),
        output_fn=outputs.append,
    )

    assert code == 0
    assert any("error:" in line for line in outputs)
