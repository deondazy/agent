import httpx
import pytest

import denosysbot.installer as installer
from denosysbot.adapters.models.base import ProviderError
from denosysbot.installer import (
    WalkthroughAnswers,
    _fetch_provider_models,
    build_env_updates,
    merge_env_content,
    run_walkthrough,
)


def _make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_build_env_updates_for_openai_anthropic_and_gemini_profile() -> None:
    answers = WalkthroughAnswers(
        profile="openai-anthropic-gemini",
        openai_api_key="sk-openai",
        anthropic_api_key="sk-anthropic",
        gemini_api_key="sk-gemini",
        openai_model="gpt-5-mini",
        anthropic_model="claude-opus-4-6",
        gemini_model="gemini-2.5-pro",
    )

    updates = build_env_updates(answers)

    assert updates["DENOSYSBOT_MODEL_FALLBACK_ORDER"] == "openai,anthropic,gemini"
    assert updates["DENOSYSBOT_MODEL_OPENAI_MODEL"] == "gpt-5-mini"
    assert updates["DENOSYSBOT_MODEL_ANTHROPIC_MODEL"] == "claude-opus-4-6"
    assert updates["DENOSYSBOT_MODEL_GEMINI_MODEL"] == "gemini-2.5-pro"
    assert updates["OPENAI_API_KEY"] == "sk-openai"
    assert updates["ANTHROPIC_API_KEY"] == "sk-anthropic"
    assert updates["GEMINI_API_KEY"] == "sk-gemini"
    assert "OLLAMA_API_KEY" not in updates


def test_fetch_provider_models_for_openai_uses_models_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/models"
        assert request.headers["authorization"] == "Bearer sk-openai"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "gpt-5"},
                    {"id": "gpt-4.1"},
                ]
            },
        )

    models = _fetch_provider_models(
        provider_name="openai",
        api_key="sk-openai",
        base_url="https://api.openai.com",
        anthropic_version="2023-06-01",
        http_client=_make_client(handler),
    )

    assert models == ["gpt-4.1", "gpt-5"]


def test_fetch_provider_models_for_gemini_filters_to_generate_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1beta/models"
        assert request.headers["x-goog-api-key"] == "sk-gemini"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-2.5-pro",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/text-embedding-004",
                        "supportedGenerationMethods": ["embedContent"],
                    },
                    {
                        "name": "models/gemini-2.5-flash",
                        "supportedGenerationMethods": ["countTokens", "generateContent"],
                    },
                ]
            },
        )

    models = _fetch_provider_models(
        provider_name="gemini",
        api_key="sk-gemini",
        base_url="https://generativelanguage.googleapis.com",
        anthropic_version="2023-06-01",
        http_client=_make_client(handler),
    )

    assert models == ["gemini-2.5-flash", "gemini-2.5-pro"]


def test_fetch_provider_models_raises_when_required_api_key_missing() -> None:
    with pytest.raises(ProviderError, match="API key is required"):
        _fetch_provider_models(
            provider_name="anthropic",
            api_key=None,
            base_url="https://api.anthropic.com",
            anthropic_version="2023-06-01",
        )


def test_build_env_updates_for_ollama_profile() -> None:
    answers = WalkthroughAnswers(
        profile="ollama-only",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5-coder:14b",
    )

    updates = build_env_updates(answers)

    assert updates["DENOSYSBOT_MODEL_FALLBACK_ORDER"] == "ollama"
    assert updates["DENOSYSBOT_MODEL_OLLAMA_BASE_URL"] == "http://localhost:11434"
    assert updates["DENOSYSBOT_MODEL_OLLAMA_MODEL"] == "qwen2.5-coder:14b"


def test_merge_env_content_updates_existing_values_and_preserves_lines() -> None:
    existing = "# existing\nDENOSYSBOT_MODEL_FALLBACK_ORDER=openai\nFOO=bar\n"
    updates = {
        "DENOSYSBOT_MODEL_FALLBACK_ORDER": "openai,anthropic,ollama",
        "OPENAI_API_KEY": "sk-test",
    }

    merged = merge_env_content(existing, updates)

    assert "# existing" in merged
    assert "FOO=bar" in merged
    assert "DENOSYSBOT_MODEL_FALLBACK_ORDER=openai,anthropic,ollama" in merged
    assert "OPENAI_API_KEY=sk-test" in merged


def test_run_walkthrough_uses_textual_app_result(monkeypatch, tmp_path) -> None:
    env_path = tmp_path / ".env"
    answers = WalkthroughAnswers(
        profile="openai-only",
        openai_api_key="sk-openai",
        openai_model="gpt-5-mini",
        openai_base_url="https://api.openai.com",
    )
    launched: dict[str, object] = {}

    class FakeTextualConfigApp:
        def __init__(self, *, env_path):
            launched["env_path"] = env_path

        def run(self):
            launched["ran"] = True
            return answers

    monkeypatch.setattr(installer, "ConfigWalkthroughApp", FakeTextualConfigApp)

    run_walkthrough(env_path)

    written = env_path.read_text()
    assert launched["env_path"] == env_path
    assert launched["ran"] is True
    assert "DENOSYSBOT_MODEL_FALLBACK_ORDER=openai" in written
    assert "OPENAI_API_KEY=sk-openai" in written
    assert "DENOSYSBOT_MODEL_OPENAI_MODEL=gpt-5-mini" in written
