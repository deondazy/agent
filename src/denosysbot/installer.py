"""Interactive installer walkthrough for DenosysBot agent."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import argparse
import os
import sys

import httpx

from denosysbot.adapters.models.base import ProviderError

try:
    import questionary
except ImportError:  # pragma: no cover - optional dependency fallback.
    questionary = None

PROFILE_ORDERS: dict[str, tuple[str, ...]] = {
    "openai-anthropic-gemini-ollama": ("openai", "anthropic", "gemini", "ollama"),
    "openai-anthropic-gemini": ("openai", "anthropic", "gemini"),
    "openai-anthropic": ("openai", "anthropic"),
    "openai-gemini": ("openai", "gemini"),
    "anthropic-gemini": ("anthropic", "gemini"),
    "openai-only": ("openai",),
    "anthropic-only": ("anthropic",),
    "gemini-only": ("gemini",),
    "ollama-only": ("ollama",),
}

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"
DEFAULT_OPENAI_MODEL = "gpt-4.1"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2"


@dataclass(slots=True)
class WalkthroughAnswers:
    profile: str
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    ollama_api_key: str | None = None
    openai_base_url: str = DEFAULT_OPENAI_BASE_URL
    anthropic_base_url: str = DEFAULT_ANTHROPIC_BASE_URL
    anthropic_version: str = DEFAULT_ANTHROPIC_VERSION
    gemini_base_url: str = DEFAULT_GEMINI_BASE_URL
    openai_model: str = DEFAULT_OPENAI_MODEL
    anthropic_model: str = DEFAULT_ANTHROPIC_MODEL
    gemini_model: str = DEFAULT_GEMINI_MODEL
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL
    ollama_model: str = DEFAULT_OLLAMA_MODEL


def _can_use_questionary_ui() -> bool:
    if questionary is None:
        return False
    stdin_is_tty = callable(getattr(sys.stdin, "isatty", None)) and sys.stdin.isatty()
    stdout_is_tty = callable(getattr(sys.stdout, "isatty", None)) and sys.stdout.isatty()
    return bool(stdin_is_tty and stdout_is_tty)


def _questionary_select_index(*, prompt: str, options: tuple[str, ...], default_index: int = 0) -> int:
    if not options:
        raise ValueError("options must not be empty")
    if questionary is None:
        raise RuntimeError("questionary is required for interactive selection")

    bounded_default = max(0, min(default_index, len(options) - 1))
    choices = [questionary.Choice(title=label, value=index) for index, label in enumerate(options)]
    selected = questionary.select(
        prompt,
        choices=choices,
        default=bounded_default,
        use_shortcuts=False,
        use_arrow_keys=True,
    ).ask()
    if selected is None:
        return bounded_default
    if isinstance(selected, int) and 0 <= selected < len(options):
        return selected
    return bounded_default


def _select_multiple_from_options(
    *, prompt: str, options: tuple[str, ...], default_indices: tuple[int, ...] = ()
) -> tuple[int, ...]:
    if not options:
        return ()

    if _can_use_questionary_ui():
        if questionary is None:
            raise RuntimeError("questionary is required for interactive selection")
        valid_defaults = {
            index
            for index in default_indices
            if isinstance(index, int) and 0 <= index < len(options)
        }
        choices = [
            questionary.Choice(title=label, value=index, checked=index in valid_defaults)
            for index, label in enumerate(options)
        ]
        selected = questionary.checkbox(
            prompt,
            choices=choices,
            use_shortcuts=False,
            use_arrow_keys=True,
        ).ask()
        if not selected:
            return tuple(sorted(valid_defaults))
        valid_selected = {
            index
            for index in selected
            if isinstance(index, int) and 0 <= index < len(options)
        }
        return tuple(sorted(valid_selected))

    default_labels = ", ".join(options[index] for index in default_indices if 0 <= index < len(options))
    if default_labels:
        print(f"{prompt} [{default_labels}]")
    else:
        print(prompt)
    print("Enter comma-separated option numbers, or press enter for defaults:")
    for index, label in enumerate(options, start=1):
        suffix = " (default)" if (index - 1) in default_indices else ""
        print(f"{index}) {label}{suffix}")

    while True:
        raw = input("Selections: ").strip()
        if not raw:
            return tuple(sorted(index for index in default_indices if 0 <= index < len(options)))
        tokens = [token.strip() for token in raw.split(",") if token.strip()]
        parsed: list[int] = []
        invalid = False
        for token in tokens:
            if not token.isdigit():
                invalid = True
                break
            numeric = int(token)
            if numeric < 1 or numeric > len(options):
                invalid = True
                break
            parsed.append(numeric - 1)
        if invalid:
            print(f"Invalid selection. Please enter numbers between 1 and {len(options)}.")
            continue
        return tuple(sorted(set(parsed)))


def build_env_updates(answers: WalkthroughAnswers) -> dict[str, str]:
    if answers.profile not in PROFILE_ORDERS:
        raise ValueError(f"unsupported profile: {answers.profile}")

    selected_providers = PROFILE_ORDERS[answers.profile]
    updates: dict[str, str] = {
        "DENOSYSBOT_MODEL_FALLBACK_ORDER": ",".join(selected_providers),
    }

    if "openai" in selected_providers:
        updates["DENOSYSBOT_MODEL_OPENAI_BASE_URL"] = answers.openai_base_url
        updates["DENOSYSBOT_MODEL_OPENAI_MODEL"] = answers.openai_model
    if "anthropic" in selected_providers:
        updates["DENOSYSBOT_MODEL_ANTHROPIC_BASE_URL"] = answers.anthropic_base_url
        updates["DENOSYSBOT_MODEL_ANTHROPIC_VERSION"] = answers.anthropic_version
        updates["DENOSYSBOT_MODEL_ANTHROPIC_MODEL"] = answers.anthropic_model
    if "gemini" in selected_providers:
        updates["DENOSYSBOT_MODEL_GEMINI_BASE_URL"] = answers.gemini_base_url
        updates["DENOSYSBOT_MODEL_GEMINI_MODEL"] = answers.gemini_model
    if "ollama" in selected_providers:
        updates["DENOSYSBOT_MODEL_OLLAMA_BASE_URL"] = answers.ollama_base_url
        updates["DENOSYSBOT_MODEL_OLLAMA_MODEL"] = answers.ollama_model

    if answers.openai_api_key:
        updates["OPENAI_API_KEY"] = answers.openai_api_key
    if answers.anthropic_api_key:
        updates["ANTHROPIC_API_KEY"] = answers.anthropic_api_key
    if answers.gemini_api_key:
        updates["GEMINI_API_KEY"] = answers.gemini_api_key
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
    choices = (
        ("openai + anthropic + gemini + ollama (recommended)", "openai-anthropic-gemini-ollama"),
        ("openai + anthropic + gemini", "openai-anthropic-gemini"),
        ("openai + anthropic", "openai-anthropic"),
        ("openai + gemini", "openai-gemini"),
        ("anthropic + gemini", "anthropic-gemini"),
        ("openai only", "openai-only"),
        ("anthropic only", "anthropic-only"),
        ("gemini only", "gemini-only"),
        ("ollama only", "ollama-only"),
    )
    labels = tuple(label for label, _profile in choices)

    if _can_use_questionary_ui():
        selected_index = _questionary_select_index(
            prompt="Select provider profile",
            options=labels,
            default_index=0,
        )
        return choices[int(selected_index)][1]

    print("\nSelect provider profile:")
    for index, label in enumerate(labels, start=1):
        print(f"{index}) {label}")

    choice_map = {str(index): profile for index, (_label, profile) in enumerate(choices, start=1)}

    while True:
        choice = input("Enter choice [1]: ").strip() or "1"
        profile = choice_map.get(choice)
        if profile:
            return profile
        print("Invalid choice. Please enter 1-9.")


def _select_model_from_options(
    *,
    provider_label: str,
    options: tuple[str, ...],
    default: str,
) -> str:
    if not options:
        return default

    default_index = options.index(default) + 1 if default in options else 1
    choice_map = {str(index): model for index, model in enumerate(options, start=1)}

    if _can_use_questionary_ui():
        selected_index = _questionary_select_index(
            prompt=f"Select {provider_label} model",
            options=options,
            default_index=default_index - 1,
        )
        return options[int(selected_index)]

    print(f"\nSelect {provider_label} model:")
    for index, model in enumerate(options, start=1):
        suffix = " (default)" if index == default_index else ""
        print(f"{index}) {model}{suffix}")

    while True:
        choice = input(f"Enter choice [{default_index}]: ").strip() or str(default_index)
        selected = choice_map.get(choice)
        if selected:
            return selected
        print(f"Invalid choice. Please enter 1-{len(options)}.")


def _request_json(
    *,
    client: httpx.Client,
    provider_name: str,
    url: str,
    headers: dict[str, str],
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        response = client.get(url, headers=headers, params=params)
    except httpx.RequestError as exc:
        raise ProviderError(f"{provider_name} request failed: {exc}") from exc

    if response.status_code >= 400:
        raise ProviderError(
            f"{provider_name} API error ({response.status_code}): {_extract_error_message(response)}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderError(f"{provider_name} returned non-JSON response") from exc

    if not isinstance(payload, dict):
        raise ProviderError(f"{provider_name} returned unexpected JSON payload")
    return payload


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or f"HTTP {response.status_code}"

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
        if isinstance(error, str) and error:
            return error
        message = payload.get("message")
        if isinstance(message, str) and message:
            return message

    return response.text.strip() or f"HTTP {response.status_code}"


def _fetch_provider_models(
    *,
    provider_name: str,
    api_key: str | None,
    base_url: str,
    anthropic_version: str,
    http_client: httpx.Client | None = None,
) -> list[str]:
    normalized = provider_name.strip().lower()

    if normalized in {"openai", "anthropic", "gemini"} and not api_key:
        raise ProviderError(f"{normalized} API key is required to query available models")

    if http_client is None:
        with httpx.Client(timeout=20.0) as client:
            return _fetch_provider_models(
                provider_name=normalized,
                api_key=api_key,
                base_url=base_url,
                anthropic_version=anthropic_version,
                http_client=client,
            )

    models: list[str] = []
    clean_base_url = base_url.rstrip("/")

    if normalized == "openai":
        payload = _request_json(
            client=http_client,
            provider_name=normalized,
            url=f"{clean_base_url}/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        data = payload.get("data")
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                model_id = item.get("id")
                if isinstance(model_id, str) and model_id.strip():
                    models.append(model_id.strip())

    elif normalized == "anthropic":
        after_id: str | None = None
        seen_after_ids: set[str] = set()
        while True:
            params: dict[str, str] = {"limit": "100"}
            if after_id:
                params["after_id"] = after_id

            payload = _request_json(
                client=http_client,
                provider_name=normalized,
                url=f"{clean_base_url}/v1/models",
                headers={
                    "x-api-key": api_key or "",
                    "anthropic-version": anthropic_version,
                },
                params=params,
            )

            data = payload.get("data")
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    model_id = item.get("id")
                    if isinstance(model_id, str) and model_id.strip():
                        models.append(model_id.strip())

            has_more = payload.get("has_more")
            last_id = payload.get("last_id")
            if not has_more or not isinstance(last_id, str) or not last_id:
                break
            if last_id in seen_after_ids:
                break
            seen_after_ids.add(last_id)
            after_id = last_id

    elif normalized == "gemini":
        page_token: str | None = None
        while True:
            params = {"pageSize": "1000"}
            if page_token:
                params["pageToken"] = page_token

            payload = _request_json(
                client=http_client,
                provider_name=normalized,
                url=f"{clean_base_url}/v1beta/models",
                headers={"x-goog-api-key": api_key or ""},
                params=params,
            )

            raw_models = payload.get("models")
            if isinstance(raw_models, list):
                for item in raw_models:
                    if not isinstance(item, dict):
                        continue
                    methods = item.get("supportedGenerationMethods")
                    if not isinstance(methods, list) or "generateContent" not in methods:
                        continue

                    model_name = item.get("name")
                    if not isinstance(model_name, str) or not model_name.strip():
                        continue

                    cleaned_name = model_name.strip()
                    if cleaned_name.startswith("models/"):
                        cleaned_name = cleaned_name[len("models/") :]
                    if cleaned_name:
                        models.append(cleaned_name)

            next_page_token = payload.get("nextPageToken")
            if not isinstance(next_page_token, str) or not next_page_token:
                break
            page_token = next_page_token

    elif normalized == "ollama":
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = _request_json(
            client=http_client,
            provider_name=normalized,
            url=f"{clean_base_url}/api/tags",
            headers=headers,
        )
        raw_models = payload.get("models")
        if isinstance(raw_models, list):
            for item in raw_models:
                if not isinstance(item, dict):
                    continue
                model_name = item.get("name")
                if isinstance(model_name, str) and model_name.strip():
                    models.append(model_name.strip())

    else:
        raise ValueError(f"unknown provider: {provider_name}")

    unique_models = sorted(set(models))
    if not unique_models:
        raise ProviderError(f"{normalized} returned no selectable models")
    return unique_models


def _collect_answers() -> WalkthroughAnswers:
    profile = _select_profile()
    selected_providers = PROFILE_ORDERS[profile]

    openai_key = None
    anthropic_key = None
    gemini_key = None
    ollama_key = None
    openai_base_url = DEFAULT_OPENAI_BASE_URL
    anthropic_base_url = DEFAULT_ANTHROPIC_BASE_URL
    anthropic_version = DEFAULT_ANTHROPIC_VERSION
    gemini_base_url = DEFAULT_GEMINI_BASE_URL
    openai_model = DEFAULT_OPENAI_MODEL
    anthropic_model = DEFAULT_ANTHROPIC_MODEL
    gemini_model = DEFAULT_GEMINI_MODEL
    ollama_base_url = DEFAULT_OLLAMA_BASE_URL
    ollama_model = DEFAULT_OLLAMA_MODEL

    if "openai" in selected_providers:
        openai_key = _prompt("OpenAI API key (optional if already exported)", "") or None
        openai_base_url = _prompt("OpenAI base URL", DEFAULT_OPENAI_BASE_URL)
        available_models = _fetch_provider_models(
            provider_name="openai",
            api_key=openai_key or os.getenv("OPENAI_API_KEY"),
            base_url=openai_base_url,
            anthropic_version=DEFAULT_ANTHROPIC_VERSION,
        )
        openai_model = _select_model_from_options(
            provider_label="OpenAI",
            options=tuple(available_models),
            default=DEFAULT_OPENAI_MODEL if DEFAULT_OPENAI_MODEL in available_models else available_models[0],
        )

    if "anthropic" in selected_providers:
        anthropic_key = _prompt("Anthropic API key (optional if already exported)", "") or None
        anthropic_base_url = _prompt("Anthropic base URL", DEFAULT_ANTHROPIC_BASE_URL)
        anthropic_version = _prompt("Anthropic API version", DEFAULT_ANTHROPIC_VERSION)
        available_models = _fetch_provider_models(
            provider_name="anthropic",
            api_key=anthropic_key or os.getenv("ANTHROPIC_API_KEY"),
            base_url=anthropic_base_url,
            anthropic_version=anthropic_version,
        )
        anthropic_model = _select_model_from_options(
            provider_label="Anthropic",
            options=tuple(available_models),
            default=DEFAULT_ANTHROPIC_MODEL
            if DEFAULT_ANTHROPIC_MODEL in available_models
            else available_models[0],
        )

    if "gemini" in selected_providers:
        gemini_key = _prompt("Gemini API key (optional if already exported)", "") or None
        gemini_base_url = _prompt("Gemini base URL", DEFAULT_GEMINI_BASE_URL)
        available_models = _fetch_provider_models(
            provider_name="gemini",
            api_key=gemini_key or os.getenv("GEMINI_API_KEY"),
            base_url=gemini_base_url,
            anthropic_version=DEFAULT_ANTHROPIC_VERSION,
        )
        gemini_model = _select_model_from_options(
            provider_label="Gemini",
            options=tuple(available_models),
            default=DEFAULT_GEMINI_MODEL if DEFAULT_GEMINI_MODEL in available_models else available_models[0],
        )

    if "ollama" in selected_providers:
        ollama_base_url = _prompt("Ollama base URL", DEFAULT_OLLAMA_BASE_URL)
        ollama_key = _prompt("Ollama API key (optional)", "") or None
        available_models = _fetch_provider_models(
            provider_name="ollama",
            api_key=ollama_key or os.getenv("OLLAMA_API_KEY"),
            base_url=ollama_base_url,
            anthropic_version=DEFAULT_ANTHROPIC_VERSION,
        )
        ollama_model = _select_model_from_options(
            provider_label="Ollama",
            options=tuple(available_models),
            default=DEFAULT_OLLAMA_MODEL if DEFAULT_OLLAMA_MODEL in available_models else available_models[0],
        )

    return WalkthroughAnswers(
        profile=profile,
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
        gemini_api_key=gemini_key,
        ollama_api_key=ollama_key,
        openai_base_url=openai_base_url,
        anthropic_base_url=anthropic_base_url,
        anthropic_version=anthropic_version,
        gemini_base_url=gemini_base_url,
        openai_model=openai_model,
        anthropic_model=anthropic_model,
        gemini_model=gemini_model,
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
