"""Command-line entrypoints for DenosysBot."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
import argparse
import os

from denosysbot.adapters.models.base import ProviderError
from denosysbot.adapters.models.factory import build_model_gateway
from denosysbot.core.config import get_settings
from denosysbot.installer import run_walkthrough

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.widgets import Footer, Header, Input, RichLog, Static

    _TEXTUAL_IMPORT_ERROR: Exception | None = None
except ImportError as exc:  # pragma: no cover - exercised only when dependency missing.
    App = None  # type: ignore[assignment]
    ComposeResult = Any  # type: ignore[assignment]
    Binding = None  # type: ignore[assignment]
    Footer = Header = Input = RichLog = Static = None  # type: ignore[assignment]
    _TEXTUAL_IMPORT_ERROR = exc


def load_env_file(path: Path = Path(".env")) -> None:
    """Load KEY=VALUE pairs from a local env file without overriding existing env vars."""

    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def build_chat_prompt(history: list[tuple[str, str]], user_message: str) -> str:
    """Render conversation context into a provider-friendly prompt."""

    lines = [
        "You are DenosysBot, a concise coding assistant operating in a terminal.",
        "Respond with actionable answers.",
        "",
    ]

    if history:
        lines.append("Conversation so far:")
        for role, content in history[-10:]:
            lines.append(f"{role}: {content}")
        lines.append("")

    lines.append(f"user: {user_message}")
    lines.append("assistant:")
    return "\n".join(lines)


def _raise_textual_missing() -> None:
    raise RuntimeError(
        "textual is required for `denosysbot tui`. Install dependencies with: pip install -e .[dev]"
    ) from _TEXTUAL_IMPORT_ERROR


if _TEXTUAL_IMPORT_ERROR is None:

    class DenosysBotTUIApp(App[None]):
        """Textual-powered interactive chat interface."""

        CSS = """
        Screen {
            layout: vertical;
        }

        #title {
            padding: 0 1;
        }

        #chat-log {
            height: 1fr;
            border: solid $primary;
            margin: 0 1;
        }

        #chat-input {
            margin: 0 1 1 1;
        }
        """

        BINDINGS = [
            Binding("ctrl+c", "quit_chat", "Quit"),
            Binding("ctrl+r", "reset_chat", "Reset"),
        ]

        def __init__(self, *, gateway) -> None:
            super().__init__()
            self._gateway = gateway
            self._history: list[tuple[str, str]] = []

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static("DenoSysBot TUI | Commands: /help, /reset, /exit", id="title")
            yield RichLog(id="chat-log", wrap=True, highlight=False, markup=False)
            yield Input(placeholder="Type a message and press Enter", id="chat-input")
            yield Footer()

        def on_mount(self) -> None:
            self.query_one("#chat-input", Input).focus()
            self._write_line("DenoSysBot is your terminal AI assistant.")

        def _write_line(self, message: str) -> None:
            self.query_one("#chat-log", RichLog).write(message)

        def action_quit_chat(self) -> None:
            self._write_line("Goodbye.")
            self.exit()

        def action_reset_chat(self) -> None:
            self._history.clear()
            self._write_line("Conversation reset.")

        def on_input_submitted(self, event: Input.Submitted) -> None:
            user_message = event.value.strip()
            event.input.value = ""

            if not user_message:
                return

            lowered = user_message.lower()
            if lowered in {"/exit", "exit", "quit"}:
                self.action_quit_chat()
                return

            if lowered == "/help":
                self._write_line("Commands: /help, /reset, /exit")
                return

            if lowered == "/reset":
                self.action_reset_chat()
                return

            self._write_line(f"you> {user_message}")
            prompt = build_chat_prompt(self._history, user_message)
            self._write_line("denosysbot> thinking...")

            try:
                response = self._gateway.generate(prompt)
            except ProviderError as exc:
                self._write_line(f"denosysbot> error: {exc}")
                return

            self._write_line(f"denosysbot> {response}")
            self._history.append(("user", user_message))
            self._history.append(("assistant", response))

else:

    class DenosysBotTUIApp:  # pragma: no cover - fallback only used when dependency missing.
        def __init__(self, *, gateway) -> None:
            self._gateway = gateway
            _raise_textual_missing()

        def run(self) -> None:
            _raise_textual_missing()


def run_tui(
    *,
    gateway=None,
    app_cls: Callable[..., Any] = DenosysBotTUIApp,
) -> int:
    """Run interactive Textual chat app."""

    if gateway is None:
        load_env_file(Path(".env"))
        get_settings.cache_clear()
        gateway = build_model_gateway(get_settings())

    app = app_cls(gateway=gateway)
    app.run()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="denosysbot", description="DenosysBot CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("tui", help="Open interactive chat TUI")
    config_parser = subparsers.add_parser("config", help="Run guided configuration walkthrough")
    config_parser.add_argument("--env-file", default=".env", help="Path to env file to update")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "tui":
        return run_tui()

    if args.command == "config":
        run_walkthrough(Path(args.env_file))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
