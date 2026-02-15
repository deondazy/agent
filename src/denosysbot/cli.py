"""Command-line entrypoints for DenosysBot."""

from collections.abc import Callable, Sequence
from pathlib import Path
import argparse
import os
import threading
import sys

from denosysbot.adapters.models.base import ProviderError
from denosysbot.adapters.models.factory import build_model_gateway
from denosysbot.core.config import get_settings
from denosysbot.installer import run_walkthrough

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

PROGRESS_PHRASES: tuple[str, ...] = (
    "thinking",
    "working through it",
    "drafting a response",
    "checking options",
)
ELLIPSIS_FRAMES: tuple[str, ...] = (".", "..", "...")


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
    progress_interval_seconds: float = 0.35,
    progress_phrase_interval_seconds: float = 1.4,
    inplace_progress: bool | None = None,
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
    progress_phrase_index = 0
    progress_interval_seconds = max(progress_interval_seconds, 0.01)
    progress_phrase_interval_seconds = max(
        progress_phrase_interval_seconds, progress_interval_seconds
    )
    phrase_hold_ticks = max(
        1,
        round(progress_phrase_interval_seconds / progress_interval_seconds),
    )
    use_inplace_progress = output_fn is print if inplace_progress is None else inplace_progress

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
        stop_progress = threading.Event()
        progress_line_length = 0
        progress_line_lock = threading.Lock()

        def _progress_message(step: int) -> str:
            phrase_offset = step // phrase_hold_ticks
            phrase = PROGRESS_PHRASES[
                (progress_phrase_index + phrase_offset) % len(PROGRESS_PHRASES)
            ]
            ellipsis = ELLIPSIS_FRAMES[step % len(ELLIPSIS_FRAMES)]
            return f"denosysbot> {phrase}{ellipsis}"

        def _emit_progress(message: str) -> None:
            nonlocal progress_line_length
            if use_inplace_progress:
                with progress_line_lock:
                    padded = message.ljust(progress_line_length)
                    sys.stdout.write(f"\r{padded}")
                    sys.stdout.flush()
                    progress_line_length = max(progress_line_length, len(message))
                return
            output_fn(message)

        def _clear_progress_line() -> None:
            nonlocal progress_line_length
            if not use_inplace_progress:
                return
            with progress_line_lock:
                if progress_line_length == 0:
                    return
                sys.stdout.write(f"\r{' ' * progress_line_length}\r")
                sys.stdout.flush()
                progress_line_length = 0

        _emit_progress(_progress_message(0))

        def _emit_progress_updates() -> None:
            step = 1
            while not stop_progress.wait(progress_interval_seconds):
                _emit_progress(_progress_message(step))
                step += 1

        progress_thread = threading.Thread(target=_emit_progress_updates, daemon=True)
        progress_thread.start()
        response: str | None = None
        provider_error: ProviderError | None = None
        try:
            response = gateway.generate(prompt)
        except ProviderError as exc:
            provider_error = exc
        finally:
            stop_progress.set()
            progress_thread.join()
            _clear_progress_line()

        progress_phrase_index = (progress_phrase_index + 1) % len(PROGRESS_PHRASES)

        if provider_error is not None:
            output_fn(f"denosysbot> error: {provider_error}")
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
