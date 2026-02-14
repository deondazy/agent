"""Interactive installer walkthrough for DenosysBot agent."""

from dataclasses import dataclass
from pathlib import Path
import argparse

PROFILE_ORDERS: dict[str, tuple[str, ...]] = {
    "openai-anthropic-ollama": ("openai", "anthropic", "ollama"),
    "openai-anthropic": ("openai", "anthropic"),
    "openai-only": ("openai",),
    "ollama-only": ("ollama",),
}


@dataclass(slots=True)
class WalkthroughAnswers:
    profile: str
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    ollama_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"


def build_env_updates(answers: WalkthroughAnswers) -> dict[str, str]:
    if answers.profile not in PROFILE_ORDERS:
        raise ValueError(f"unsupported profile: {answers.profile}")

    updates: dict[str, str] = {
        "DENOSYSBOT_MODEL_FALLBACK_ORDER": ",".join(PROFILE_ORDERS[answers.profile]),
        "DENOSYSBOT_MODEL_OLLAMA_BASE_URL": answers.ollama_base_url,
        "DENOSYSBOT_MODEL_OLLAMA_MODEL": answers.ollama_model,
    }

    if answers.openai_api_key:
        updates["OPENAI_API_KEY"] = answers.openai_api_key
    if answers.anthropic_api_key:
        updates["ANTHROPIC_API_KEY"] = answers.anthropic_api_key
    if answers.ollama_api_key:
        updates["OLLAMA_API_KEY"] = answers.ollama_api_key

    return updates


def merge_env_content(existing_content: str, updates: dict[str, str]) -> str:
    lines = existing_content.splitlines()
    updated_keys: set[str] = set()
    merged_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            merged_lines.append(line)
            continue

        key, _sep, _value = line.partition("=")
        key = key.strip()
        if key in updates:
            merged_lines.append(f"{key}={updates[key]}")
            updated_keys.add(key)
        else:
            merged_lines.append(line)

    for key in sorted(updates.keys() - updated_keys):
        merged_lines.append(f"{key}={updates[key]}")

    output = "\n".join(merged_lines)
    if output and not output.endswith("\n"):
        output += "\n"
    return output


def _prompt(message: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{message}{suffix}: ").strip()
    if value:
        return value
    return default or ""


def _select_profile() -> str:
    print("\nSelect provider profile:")
    print("1) openai + anthropic + ollama (recommended)")
    print("2) openai + anthropic")
    print("3) openai only")
    print("4) ollama only")

    choice_map = {
        "1": "openai-anthropic-ollama",
        "2": "openai-anthropic",
        "3": "openai-only",
        "4": "ollama-only",
    }

    while True:
        choice = input("Enter choice [1]: ").strip() or "1"
        profile = choice_map.get(choice)
        if profile:
            return profile
        print("Invalid choice. Please enter 1, 2, 3, or 4.")


def _collect_answers() -> WalkthroughAnswers:
    profile = _select_profile()

    openai_key = None
    anthropic_key = None
    ollama_key = None

    if "openai" in PROFILE_ORDERS[profile]:
        openai_key = _prompt("OpenAI API key (optional if already exported)", "") or None

    if "anthropic" in PROFILE_ORDERS[profile]:
        anthropic_key = _prompt("Anthropic API key (optional if already exported)", "") or None

    ollama_base_url = _prompt("Ollama base URL", "http://localhost:11434")
    ollama_model = _prompt("Ollama model", "llama3.2")

    if "ollama" in PROFILE_ORDERS[profile]:
        ollama_key = _prompt("Ollama API key (optional)", "") or None

    return WalkthroughAnswers(
        profile=profile,
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
        ollama_api_key=ollama_key,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_model,
    )


def run_walkthrough(env_path: Path) -> None:
    print("\nAgent Installer Walkthrough")
    print("===========================")
    print("This will update your local .env for provider and gateway settings.\n")

    answers = _collect_answers()
    updates = build_env_updates(answers)

    existing = env_path.read_text() if env_path.exists() else ""
    merged = merge_env_content(existing, updates)
    env_path.write_text(merged)

    print(f"\nWrote configuration to: {env_path}")
    print("\nNext steps:")
    print("1) source .venv/bin/activate")
    print("2) uvicorn denosysbot.main:app --reload")
    print("3) (optional) redis-server")
    print("4) (optional) celery -A denosysbot.queue.celery_app worker --loglevel=INFO")
    print("5) curl http://127.0.0.1:8000/health")


def main() -> None:
    parser = argparse.ArgumentParser(description="DenosysBot installer walkthrough")
    parser.add_argument("--env-file", default=".env", help="Path to env file to update")
    args = parser.parse_args()

    run_walkthrough(Path(args.env_file))


if __name__ == "__main__":
    main()
