"""Command-line entrypoints for DenosysBot."""

from collections.abc import Callable, Sequence
from pathlib import Path
import argparse
import os

from denosysbot.adapters.models.base import ProviderError
from denosysbot.adapters.models.factory import build_model_gateway
from denosysbot.core.config import get_settings
from denosysbot.installer import run_walkthrough

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


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


def run_tui(
    *,
    gateway=None,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
) -> int:
    """Run interactive terminal chat loop."""

    if gateway is None:
        load_env_file(Path(".env"))
        get_settings.cache_clear()
        gateway = build_model_gateway(get_settings())

    output_fn("DenoSysBot TUI")
    output_fn("DenoSysBot is your terminal AI assistant.")
    output_fn("Commands: /help, /reset, /exit")

    history: list[tuple[str, str]] = []

    while True:
        try:
            user_message = input_fn("").strip()
        except EOFError:
            output_fn("Goodbye.")
            return 0

        if not user_message:
            continue

        lowered = user_message.lower()
        if lowered in {"/exit", "exit", "quit"}:
            output_fn("Goodbye.")
            return 0

        if lowered == "/help":
            output_fn("Commands: /help, /reset, /exit")
            continue

        if lowered == "/reset":
            history.clear()
            output_fn("Conversation reset.")
            continue

        prompt = build_chat_prompt(history, user_message)

        try:
            response = gateway.generate(prompt)
        except ProviderError as exc:
            output_fn(f"denosysbot> error: {exc}")
            continue

        output_fn(f"denosysbot> {response}")
        history.append(("user", user_message))
        history.append(("assistant", response))


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
