"""Command-line entrypoints for DenosysBot."""

from collections.abc import Callable, Sequence
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import argparse
import json
import math
import os
import re
import threading
import sys

from denosysbot.adapters.models.base import ProviderError
from denosysbot.adapters.models.factory import build_model_gateway
from denosysbot.core.config import get_settings
from denosysbot.installer import run_walkthrough
from denosysbot.skills.engine import (
    create_skill_folder,
    create_skill_file,
    load_skills,
    match_skills,
    render_skill_context,
    update_skill_file,
)
from denosysbot.tools.web import (
    build_crawl_context,
    build_web_context,
    crawl_docs_site,
    extract_urls,
)

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

PROGRESS_PHRASES: tuple[str, ...] = (
    "thinking",
    "working through it",
    "drafting a response",
    "checking options",
    "reviewing your request",
    "organizing the approach",
    "mapping out the answer",
    "preparing a clear response",
    "checking context",
    "lining up the next step",
    "sorting through possibilities",
    "pulling the key details together",
    "refining the response",
    "double-checking the output",
    "finalizing the wording",
    "wrapping this up",
    "making sure this is accurate",
    "keeping it concise",
    "sanity-checking before reply",
    "readying the final response",
)
ELLIPSIS_FRAMES: tuple[str, ...] = (".", "..", "...")
BOT_NAME = "DenoSysBot"
ANSI_BOLD = "\033[1m"
ANSI_RESET = "\033[0m"
DEFAULT_HISTORY_PATH = Path.home() / ".denosysbot" / "history.json"
HISTORY_PATH_ENV_VAR = "DENOSYSBOT_CHAT_HISTORY_PATH"
DEFAULT_SKILLS_PATH = Path.home() / ".denosysbot" / "skills"
SKILLS_PATH_ENV_VAR = "DENOSYSBOT_SKILLS_DIR"
ENABLE_WEB_BROWSE_ENV_VAR = "DENOSYSBOT_ENABLE_WEB_BROWSE"
AUTO_WEB_BROWSE_HINTS: tuple[str, ...] = (
    "search",
    "browse",
    "look up",
    "lookup",
    "latest",
    "current",
    "today",
    "news",
    "price",
)
WORD_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{1,}")
SKILL_CREATE_HINTS: tuple[str, ...] = (
    "create a skill",
    "make a skill",
    "build a skill",
    "create skill",
)


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


def build_chat_prompt(
    history: list[tuple[str, str]],
    user_message: str,
    *,
    context_blocks: list[str] | None = None,
) -> str:
    """Render conversation context into a provider-friendly prompt."""

    now_local = datetime.now().astimezone()
    offset = now_local.strftime("%z")
    if len(offset) == 5:
        offset = f"{offset[:3]}:{offset[3:]}"
    timezone_name = now_local.tzname() or "local"
    local_timestamp = now_local.strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "You are DenosysBot, a concise coding assistant operating in a terminal.",
        "Respond with actionable answers.",
        "Treat the provided conversation history as persistent memory across sessions.",
        "If the user asks what you remember, use the history directly.",
        f"Current local date/time: {local_timestamp} {timezone_name} ({offset})",
        "Use this timestamp as authoritative for 'now' unless the user asks for a different timezone.",
        "Never guess date/time values.",
        "",
    ]

    if context_blocks:
        lines.append("Runtime context:")
        for block in context_blocks:
            payload = block.strip()
            if payload:
                lines.append(payload)
                lines.append("")

    if history:
        lines.append("Conversation so far:")
        for role, content in history:
            lines.append(f"{role}: {content}")
        lines.append("")

    lines.append(f"user: {user_message}")
    lines.append("assistant:")
    return "\n".join(lines)


def resolve_history_path(path: Path | None = None) -> Path:
    """Resolve chat history path from explicit value, env, or default location."""

    if path is not None:
        return path

    configured = os.getenv(HISTORY_PATH_ENV_VAR)
    if configured:
        return Path(configured).expanduser()

    return DEFAULT_HISTORY_PATH


def resolve_skills_path(path: Path | None = None) -> Path:
    """Resolve local skills directory from explicit value, env, or default path."""

    if path is not None:
        return path

    configured = os.getenv(SKILLS_PATH_ENV_VAR)
    if configured:
        return Path(configured).expanduser()

    return DEFAULT_SKILLS_PATH


def load_chat_history(path: Path) -> list[tuple[str, str]]:
    """Read persisted chat history, returning only valid role/content pairs."""

    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(payload, list):
        return []

    history: list[tuple[str, str]] = []
    for item in payload:
        if isinstance(item, dict):
            role = item.get("role")
            content = item.get("content")
            if isinstance(role, str) and isinstance(content, str):
                history.append((role, content))
        elif isinstance(item, list | tuple) and len(item) == 2:
            role, content = item
            if isinstance(role, str) and isinstance(content, str):
                history.append((role, content))

    return history


def persist_chat_history(path: Path, history: list[tuple[str, str]]) -> None:
    """Write chat history to disk, ignoring persistence errors."""

    payload = [{"role": role, "content": content} for role, content in history]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{json.dumps(payload, ensure_ascii=True, indent=2)}\n")
    except OSError:
        return


def _parse_skill_create_payload(payload: str) -> tuple[str, str, tuple[str, ...]] | None:
    sections = [section.strip() for section in payload.split("|")]
    if len(sections) < 2:
        return None

    name = sections[0]
    description = sections[1]
    if not name or not description:
        return None

    triggers: tuple[str, ...] = ()
    if len(sections) >= 3:
        raw = [item.strip() for item in sections[2].split(",")]
        triggers = tuple(item for item in raw if item)
    return name, description, triggers


def _parse_skill_learn_payload(payload: str) -> tuple[str, str] | None:
    sections = [section.strip() for section in payload.split("|")]
    if len(sections) < 2:
        return None
    name, topic = sections[0], sections[1]
    if not name or not topic:
        return None
    return name, topic


def _extract_keywords(value: str, *, max_keywords: int = 8) -> tuple[str, ...]:
    keywords: list[str] = []
    for token in WORD_PATTERN.findall(value.lower()):
        if token not in keywords:
            keywords.append(token)
    return tuple(keywords[:max_keywords]) or ("skill",)


def _is_web_browse_enabled() -> bool:
    raw = os.getenv(ENABLE_WEB_BROWSE_ENV_VAR, "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _should_auto_browse_web(user_message: str) -> bool:
    lowered = user_message.lower()
    return any(hint in lowered for hint in AUTO_WEB_BROWSE_HINTS)


def _contains_skill_create_request(user_message: str) -> bool:
    lowered = user_message.lower()
    return any(hint in lowered for hint in SKILL_CREATE_HINTS)


def _suggest_skill_name(user_message: str, urls: tuple[str, ...]) -> str:
    for url in urls:
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        lowered_parts = [part.lower() for part in parts]
        if parsed.netloc.endswith("filamentphp.com") and "5.x" in lowered_parts:
            return "filament-v5"
        if lowered_parts:
            candidate = lowered_parts[-1].replace(".", "-")
            candidate = re.sub(r"[^a-z0-9-]+", "-", candidate).strip("-")
            if candidate:
                return candidate

    keywords = [token for token in WORD_PATTERN.findall(user_message.lower()) if token not in {"skill", "create"}]
    if not keywords:
        return "learned-skill"
    return "-".join(keywords[:3])


def _build_learned_skill_body(reference_context: str) -> str:
    lines = [
        "# Workflow",
        "",
        "1. Review listed references before acting.",
        "2. Use reference facts instead of assumptions.",
        "3. Verify final output against source details.",
        "",
        "## Learned References",
        "",
        reference_context.strip(),
    ]
    return "\n".join(lines)


def _build_learned_skill_description(user_message: str, urls: tuple[str, ...], skill_name: str) -> str:
    if urls:
        parsed = urlparse(urls[0])
        host = parsed.netloc
        return (
            f"Agentic documentation skill for {skill_name}. Use when users ask about topics from {host}. "
            "Ground answers in crawled docs pages and cite relevant sections."
        )

    topic_tokens = " ".join(_extract_keywords(user_message)[:6])
    return (
        f"Agentic learned skill for {skill_name}. Use when requests match: {topic_tokens}. "
        "Ground guidance in browsed references."
    )


def run_tui(
    *,
    gateway=None,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    progress_interval_seconds: float = 0.35,
    progress_phrase_interval_seconds: float = 4.2,
    inplace_progress: bool | None = None,
    history_path: Path | None = None,
    skills_path: Path | None = None,
) -> int:
    """Run interactive terminal chat loop."""

    if gateway is None:
        load_env_file(Path(".env"))
        get_settings.cache_clear()
        gateway = build_model_gateway(get_settings())

    output_fn("DenoSysBot TUI")
    output_fn("DenoSysBot is your terminal AI assistant.")
    output_fn("Commands: /help, /reset, /exit, /skills, /skill create, /skill edit, /skill learn, /web")

    resolved_history_path = resolve_history_path(history_path)
    resolved_skills_path = resolve_skills_path(skills_path)
    history = load_chat_history(resolved_history_path)
    progress_phrase_index = 0
    progress_interval_seconds = max(progress_interval_seconds, 0.01)
    progress_phrase_interval_seconds = max(
        progress_phrase_interval_seconds, progress_interval_seconds
    )
    phrase_hold_ticks = max(
        1,
        math.ceil(progress_phrase_interval_seconds / progress_interval_seconds),
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
            output_fn("Commands: /help, /reset, /exit, /skills, /skill create, /skill edit, /skill learn, /web")
            continue

        if lowered == "/reset":
            history.clear()
            persist_chat_history(resolved_history_path, history)
            output_fn("Conversation reset.")
            continue

        if lowered == "/skills":
            skills = load_skills(resolved_skills_path)
            if not skills:
                output_fn("No skills found.")
                continue
            output_fn(f"Skills ({len(skills)}):")
            for skill in skills:
                output_fn(f"- {skill.name}: {skill.description}")
            continue

        if lowered.startswith("/skill create "):
            parsed = _parse_skill_create_payload(user_message[len("/skill create ") :].strip())
            if parsed is None:
                output_fn("Usage: /skill create <name> | <description> | <trigger1,trigger2>")
                continue
            name, description, triggers = parsed
            created = create_skill_file(
                skills_dir=resolved_skills_path,
                name=name,
                description=description,
                triggers=triggers,
            )
            output_fn(f"Created skill: {created}")
            continue

        if lowered.startswith("/skill edit "):
            parsed = _parse_skill_create_payload(user_message[len("/skill edit ") :].strip())
            if parsed is None:
                output_fn("Usage: /skill edit <name> | <description> | <trigger1,trigger2>")
                continue
            name, description, triggers = parsed
            try:
                updated = update_skill_file(
                    skills_dir=resolved_skills_path,
                    name=name,
                    description=description,
                    triggers=triggers,
                )
            except FileNotFoundError:
                output_fn(f"Skill not found: {name}")
                continue
            except ValueError as exc:
                output_fn(f"Skill update failed: {exc}")
                continue
            output_fn(f"Updated skill: {updated}")
            continue

        if lowered.startswith("/skill learn "):
            parsed = _parse_skill_learn_payload(user_message[len("/skill learn ") :].strip())
            if parsed is None:
                output_fn("Usage: /skill learn <name> | <topic to research>")
                continue
            name, topic = parsed
            try:
                web_context, results = build_web_context(topic, max_results=3)
            except Exception as exc:  # pragma: no cover - network/runtime variability.
                output_fn(f"denosysbot> web error: {exc}")
                continue
            if not results:
                output_fn("denosysbot> web: no results found.")
                continue

            learned_body_lines = [
                "# Workflow",
                "",
                "1. Review sources listed below before acting.",
                "2. Apply the referenced practices to user requests.",
                "3. Verify output against source guidance.",
                "",
                "## Learned References",
                "",
                web_context,
            ]
            created = create_skill_file(
                skills_dir=resolved_skills_path,
                name=name,
                description=f"Learned guidance for {topic}",
                triggers=_extract_keywords(topic),
                body="\n".join(learned_body_lines),
            )
            output_fn(f"Created skill: {created}")
            output_fn(f"Learned from {len(results)} web result(s).")
            continue

        if lowered.startswith("/web "):
            query = user_message[len("/web ") :].strip()
            if not query:
                output_fn("Usage: /web <query>")
                continue
            try:
                _web_context, results = build_web_context(query, max_results=3)
            except Exception as exc:  # pragma: no cover - network/runtime variability.
                output_fn(f"denosysbot> web error: {exc}")
                continue
            if not results:
                output_fn("denosysbot> web: no results found.")
                continue
            output_fn("Web results:")
            for index, result in enumerate(results, start=1):
                output_fn(f"{index}. {result.title} - {result.url}")
                excerpt = getattr(result, "excerpt", "")
                if isinstance(excerpt, str) and excerpt:
                    output_fn(f"   {excerpt}")
            continue

        if _contains_skill_create_request(user_message):
            urls = extract_urls(user_message)
            skill_name = _suggest_skill_name(user_message, urls)
            try:
                if urls:
                    crawled_pages = crawl_docs_site(
                        urls[0],
                        max_pages=16,
                        max_depth=2,
                    )
                    reference_context, results = build_crawl_context(crawled_pages)
                else:
                    reference_context, results = build_web_context(user_message, max_results=3)
            except Exception as exc:  # pragma: no cover - network/runtime variability.
                output_fn(f"denosysbot> web error: {exc}")
                continue

            if not results or not reference_context.strip():
                output_fn("denosysbot> web: no usable references found for skill creation.")
                continue

            created = create_skill_folder(
                skills_dir=resolved_skills_path,
                name=skill_name,
                description=_build_learned_skill_description(user_message, urls, skill_name),
                triggers=_extract_keywords(skill_name.replace("-", " ")),
                body=_build_learned_skill_body(reference_context),
            )
            output_fn(f"Created skill: {created}")
            output_fn(f"Learned from {len(results)} source(s).")
            continue

        context_blocks: list[str] = []
        matched_skills = match_skills(user_message, load_skills(resolved_skills_path))
        skills_context = render_skill_context(matched_skills)
        if skills_context:
            context_blocks.append(skills_context)

        if _is_web_browse_enabled() and _should_auto_browse_web(user_message):
            try:
                web_context, web_results = build_web_context(user_message, max_results=3)
            except Exception:  # pragma: no cover - network/runtime variability.
                web_context = ""
                web_results = []
            if web_context and web_results:
                context_blocks.append(web_context)

        prompt = build_chat_prompt(history, user_message, context_blocks=context_blocks)
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
            history.append(("user", user_message))
            persist_chat_history(resolved_history_path, history)
            output_fn(f"denosysbot> error: {provider_error}")
            continue

        output_fn(f"{ANSI_BOLD}{BOT_NAME}{ANSI_RESET}")
        output_fn(response)
        history.append(("user", user_message))
        history.append(("assistant", response))
        persist_chat_history(resolved_history_path, history)


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
