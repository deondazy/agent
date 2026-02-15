from collections import deque
import inspect
import json
from pathlib import Path
import re
import time

from denosysbot.adapters.models.base import ProviderError
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
