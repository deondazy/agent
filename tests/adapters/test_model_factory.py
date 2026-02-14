import pytest

from denosysbot.adapters.models.anthropic import AnthropicProvider
from denosysbot.adapters.models.factory import build_model_gateway
from denosysbot.adapters.models.gemini import GeminiProvider
from denosysbot.adapters.models.ollama import OllamaProvider
from denosysbot.adapters.models.openai import OpenAIProvider
from denosysbot.core.config import Settings


def test_factory_respects_order_and_per_provider_settings() -> None:
    settings = Settings(
        model_fallback_order=("ollama", "openai", "anthropic", "gemini"),
        model_openai_model="gpt-5",
        model_openai_base_url="https://openai.example",
        model_openai_max_retries=5,
        model_anthropic_model="claude-3-5-sonnet-latest",
        model_gemini_model="gemini-2.5-pro",
        model_gemini_base_url="https://gemini.example",
        model_gemini_max_retries=7,
        model_ollama_model="qwen2.5-coder:14b",
        model_ollama_base_url="http://ollama.internal:11434",
    )

    gateway = build_model_gateway(settings)

    assert [provider.name for provider in gateway.providers] == [
        "ollama",
        "openai",
        "anthropic",
        "gemini",
    ]

    ollama = gateway.providers[0]
    openai = gateway.providers[1]
    anthropic = gateway.providers[2]
    gemini = gateway.providers[3]

    assert isinstance(ollama, OllamaProvider)
    assert isinstance(openai, OpenAIProvider)
    assert isinstance(anthropic, AnthropicProvider)
    assert isinstance(gemini, GeminiProvider)

    assert ollama.model == "qwen2.5-coder:14b"
    assert ollama.base_url == "http://ollama.internal:11434"
    assert openai.model == "gpt-5"
    assert openai.base_url == "https://openai.example"
    assert openai.max_retries == 5
    assert anthropic.model == "claude-3-5-sonnet-latest"
    assert gemini.model == "gemini-2.5-pro"
    assert gemini.base_url == "https://gemini.example"
    assert gemini.max_retries == 7


def test_factory_rejects_unknown_provider() -> None:
    settings = Settings(model_fallback_order=("openai", "unknown"))

    with pytest.raises(ValueError, match="unknown provider"):
        build_model_gateway(settings)
