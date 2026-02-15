"""Interactive installer walkthrough for DenosysBot agent."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import argparse
import os

import httpx

from denosysbot.adapters.models.base import ProviderError

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

PROFILE_CHOICES: tuple[tuple[str, str], ...] = (
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

PROVIDER_API_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "ollama": "OLLAMA_API_KEY",
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


@dataclass(slots=True)
class _PromptStep:
    kind: str
    field: str
    prompt: str
    default: str = ""
    provider_name: str | None = None
    api_key_field: str | None = None
    base_url_field: str | None = None
    options: tuple[str, ...] | None = None


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


def _raise_textual_missing_for_config() -> None:
    raise RuntimeError(
        "textual is required for `denosysbot config`. Install dependencies with: pip install -e .[dev]"
    ) from _TEXTUAL_IMPORT_ERROR


if _TEXTUAL_IMPORT_ERROR is None:

    class ConfigWalkthroughApp(App[WalkthroughAnswers | None]):
        """Textual-driven configuration walkthrough."""

        CSS = """
        Screen {
            layout: vertical;
        }

        #title {
            padding: 0 1;
        }

        #walkthrough-log {
            height: 1fr;
            border: solid $primary;
            margin: 0 1;
        }

        #walkthrough-input {
            margin: 0 1 1 1;
        }
        """

        BINDINGS = [
            Binding("ctrl+c", "cancel_walkthrough", "Cancel"),
        ]

        def __init__(self, *, env_path: Path) -> None:
            super().__init__()
            self.env_path = env_path
            self._values: dict[str, str] = {
                "profile": PROFILE_CHOICES[0][1],
                "openai_api_key": "",
                "anthropic_api_key": "",
                "gemini_api_key": "",
                "ollama_api_key": "",
                "openai_base_url": DEFAULT_OPENAI_BASE_URL,
                "anthropic_base_url": DEFAULT_ANTHROPIC_BASE_URL,
                "anthropic_version": DEFAULT_ANTHROPIC_VERSION,
                "gemini_base_url": DEFAULT_GEMINI_BASE_URL,
                "openai_model": DEFAULT_OPENAI_MODEL,
                "anthropic_model": DEFAULT_ANTHROPIC_MODEL,
                "gemini_model": DEFAULT_GEMINI_MODEL,
                "ollama_base_url": DEFAULT_OLLAMA_BASE_URL,
                "ollama_model": DEFAULT_OLLAMA_MODEL,
            }
            self._steps: list[_PromptStep] = [
                _PromptStep(
                    kind="profile",
                    field="profile",
                    prompt="Select provider profile",
                    default="1",
                )
            ]
            self._step_index = 0

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static(f"Installer Walkthrough | Target env: {self.env_path}", id="title")
            yield RichLog(id="walkthrough-log", wrap=True, highlight=False, markup=False)
            yield Input(placeholder="Answer and press Enter", id="walkthrough-input")
            yield Footer()

        def on_mount(self) -> None:
            self.query_one("#walkthrough-input", Input).focus()
            self._write("Agent Installer Walkthrough")
            self._write("This will update your local .env for provider and gateway settings.")
            self._show_current_prompt()

        def action_cancel_walkthrough(self) -> None:
            self._write("Walkthrough canceled.")
            self.exit(None)

        def _write(self, message: str) -> None:
            self.query_one("#walkthrough-log", RichLog).write(message)

        def _current_step(self) -> _PromptStep:
            return self._steps[self._step_index]

        def _set_input_placeholder(self, text: str) -> None:
            self.query_one("#walkthrough-input", Input).placeholder = text

        def _show_current_prompt(self) -> None:
            step = self._current_step()

            if step.kind == "profile":
                self._write("")
                self._write("Select provider profile:")
                for index, (label, _profile) in enumerate(PROFILE_CHOICES, start=1):
                    suffix = " (default)" if index == 1 else ""
                    self._write(f"{index}) {label}{suffix}")
                self._write("Enter choice [1]:")
                self._set_input_placeholder("1")
                return

            if step.kind == "model":
                self._ensure_model_options(step)
                options = step.options or ()
                if options:
                    default_index = options.index(step.default) + 1 if step.default in options else 1
                    self._write("")
                    self._write(f"{step.prompt}:")
                    for index, model in enumerate(options, start=1):
                        suffix = " (default)" if index == default_index else ""
                        self._write(f"{index}) {model}{suffix}")
                    self._write(f"Enter choice [{default_index}] or type model id:")
                    self._set_input_placeholder(str(default_index))
                    return

            suffix = f" [{step.default}]" if step.default else ""
            self._write("")
            self._write(f"{step.prompt}{suffix}:")
            self._set_input_placeholder(step.default or "")

        def on_input_submitted(self, event: Input.Submitted) -> None:
            raw_value = event.value.strip()
            event.input.value = ""

            step = self._current_step()

            if step.kind == "profile":
                profile = self._parse_profile(raw_value)
                if profile is None:
                    self._write(f"Invalid choice. Please enter 1-{len(PROFILE_CHOICES)}.")
                    return

                self._values["profile"] = profile
                self._steps = [self._steps[0], *self._build_steps_for_profile(profile)]
                self._advance()
                return

            if step.kind == "model":
                selected_model = self._resolve_model_selection(step, raw_value)
                if selected_model is None:
                    return
                self._values[step.field] = selected_model
                self._advance()
                return

            self._values[step.field] = raw_value or step.default
            self._advance()

        def _advance(self) -> None:
            self._step_index += 1
            if self._step_index >= len(self._steps):
                self._finish()
                return
            self._show_current_prompt()

        def _parse_profile(self, raw_value: str) -> str | None:
            if not raw_value:
                return PROFILE_CHOICES[0][1]

            normalized = raw_value.strip().lower()
            if normalized in PROFILE_ORDERS:
                return normalized

            if not normalized.isdigit():
                return None

            index = int(normalized)
            if 1 <= index <= len(PROFILE_CHOICES):
                return PROFILE_CHOICES[index - 1][1]
            return None

        def _build_steps_for_profile(self, profile: str) -> list[_PromptStep]:
            selected_providers = PROFILE_ORDERS[profile]
            steps: list[_PromptStep] = []

            if "openai" in selected_providers:
                steps.extend(
                    [
                        _PromptStep(
                            kind="text",
                            field="openai_api_key",
                            prompt="OpenAI API key (optional if already exported)",
                        ),
                        _PromptStep(
                            kind="text",
                            field="openai_base_url",
                            prompt="OpenAI base URL",
                            default=DEFAULT_OPENAI_BASE_URL,
                        ),
                        _PromptStep(
                            kind="model",
                            field="openai_model",
                            prompt="Select OpenAI model",
                            default=DEFAULT_OPENAI_MODEL,
                            provider_name="openai",
                            api_key_field="openai_api_key",
                            base_url_field="openai_base_url",
                        ),
                    ]
                )

            if "anthropic" in selected_providers:
                steps.extend(
                    [
                        _PromptStep(
                            kind="text",
                            field="anthropic_api_key",
                            prompt="Anthropic API key (optional if already exported)",
                        ),
                        _PromptStep(
                            kind="text",
                            field="anthropic_base_url",
                            prompt="Anthropic base URL",
                            default=DEFAULT_ANTHROPIC_BASE_URL,
                        ),
                        _PromptStep(
                            kind="text",
                            field="anthropic_version",
                            prompt="Anthropic API version",
                            default=DEFAULT_ANTHROPIC_VERSION,
                        ),
                        _PromptStep(
                            kind="model",
                            field="anthropic_model",
                            prompt="Select Anthropic model",
                            default=DEFAULT_ANTHROPIC_MODEL,
                            provider_name="anthropic",
                            api_key_field="anthropic_api_key",
                            base_url_field="anthropic_base_url",
                        ),
                    ]
                )

            if "gemini" in selected_providers:
                steps.extend(
                    [
                        _PromptStep(
                            kind="text",
                            field="gemini_api_key",
                            prompt="Gemini API key (optional if already exported)",
                        ),
                        _PromptStep(
                            kind="text",
                            field="gemini_base_url",
                            prompt="Gemini base URL",
                            default=DEFAULT_GEMINI_BASE_URL,
                        ),
                        _PromptStep(
                            kind="model",
                            field="gemini_model",
                            prompt="Select Gemini model",
                            default=DEFAULT_GEMINI_MODEL,
                            provider_name="gemini",
                            api_key_field="gemini_api_key",
                            base_url_field="gemini_base_url",
                        ),
                    ]
                )

            if "ollama" in selected_providers:
                steps.extend(
                    [
                        _PromptStep(
                            kind="text",
                            field="ollama_base_url",
                            prompt="Ollama base URL",
                            default=DEFAULT_OLLAMA_BASE_URL,
                        ),
                        _PromptStep(
                            kind="text",
                            field="ollama_api_key",
                            prompt="Ollama API key (optional)",
                        ),
                        _PromptStep(
                            kind="model",
                            field="ollama_model",
                            prompt="Select Ollama model",
                            default=DEFAULT_OLLAMA_MODEL,
                            provider_name="ollama",
                            api_key_field="ollama_api_key",
                            base_url_field="ollama_base_url",
                        ),
                    ]
                )

            return steps

        def _ensure_model_options(self, step: _PromptStep) -> None:
            if step.options is not None:
                return

            provider_name = step.provider_name or ""
            key_field = step.api_key_field or ""
            base_url_field = step.base_url_field or ""

            entered_api_key = self._values.get(key_field, "").strip()
            env_api_key = os.getenv(PROVIDER_API_KEY_ENV.get(provider_name, ""), "").strip()
            api_key = entered_api_key or env_api_key or None
            base_url = self._values.get(base_url_field, "").strip()
            anthropic_version = self._values.get("anthropic_version", DEFAULT_ANTHROPIC_VERSION).strip()

            try:
                models = _fetch_provider_models(
                    provider_name=provider_name,
                    api_key=api_key,
                    base_url=base_url,
                    anthropic_version=anthropic_version,
                )
            except ProviderError as exc:
                self._write(f"warning: {exc}")
                self._write("Proceeding with manual model entry.")
                step.options = ()
                return

            step.options = tuple(models)

        def _resolve_model_selection(self, step: _PromptStep, raw_value: str) -> str | None:
            options = step.options or ()
            if not options:
                return raw_value or step.default

            default_index = options.index(step.default) + 1 if step.default in options else 1
            if not raw_value:
                return options[default_index - 1]

            if raw_value.isdigit():
                selected_index = int(raw_value)
                if 1 <= selected_index <= len(options):
                    return options[selected_index - 1]
                self._write(f"Invalid model choice. Please enter 1-{len(options)} or type a model id.")
                return None

            return raw_value

        def _empty_to_none(self, value: str) -> str | None:
            normalized = value.strip()
            return normalized or None

        def _finish(self) -> None:
            answers = WalkthroughAnswers(
                profile=self._values["profile"],
                openai_api_key=self._empty_to_none(self._values["openai_api_key"]),
                anthropic_api_key=self._empty_to_none(self._values["anthropic_api_key"]),
                gemini_api_key=self._empty_to_none(self._values["gemini_api_key"]),
                ollama_api_key=self._empty_to_none(self._values["ollama_api_key"]),
                openai_base_url=self._values["openai_base_url"],
                anthropic_base_url=self._values["anthropic_base_url"],
                anthropic_version=self._values["anthropic_version"],
                gemini_base_url=self._values["gemini_base_url"],
                openai_model=self._values["openai_model"],
                anthropic_model=self._values["anthropic_model"],
                gemini_model=self._values["gemini_model"],
                ollama_base_url=self._values["ollama_base_url"],
                ollama_model=self._values["ollama_model"],
            )
            self.exit(answers)

else:

    class ConfigWalkthroughApp:  # pragma: no cover - fallback only used when dependency missing.
        def __init__(self, *, env_path: Path) -> None:
            self.env_path = env_path

        def run(self) -> WalkthroughAnswers | None:
            _raise_textual_missing_for_config()


def run_walkthrough(env_path: Path) -> None:
    app = ConfigWalkthroughApp(env_path=env_path)
    answers = app.run()
    if not isinstance(answers, WalkthroughAnswers):
        raise RuntimeError("walkthrough cancelled before writing configuration")

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
