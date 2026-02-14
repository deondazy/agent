import pytest

from openclaw_agent.adapters.models.anthropic import AnthropicProvider
from openclaw_agent.adapters.models.factory import build_model_gateway
from openclaw_agent.adapters.models.ollama import OllamaProvider
from openclaw_agent.adapters.models.openai import OpenAIProvider
from openclaw_agent.core.config import Settings


def test_factory_respects_order_and_per_provider_settings() -> None:
    settings = Settings(
        model_fallback_order=("ollama", "openai", "anthropic"),
        model_openai_model="gpt-5",
        model_openai_base_url="https://openai.example",
        model_openai_max_retries=5,
        model_anthropic_model="claude-3-5-sonnet-latest",
        model_ollama_model="qwen2.5-coder:14b",
        model_ollama_base_url="http://ollama.internal:11434",
    )

    gateway = build_model_gateway(settings)

    assert [provider.name for provider in gateway.providers] == ["ollama", "openai", "anthropic"]

    ollama = gateway.providers[0]
    openai = gateway.providers[1]
    anthropic = gateway.providers[2]

    assert isinstance(ollama, OllamaProvider)
    assert isinstance(openai, OpenAIProvider)
    assert isinstance(anthropic, AnthropicProvider)

    assert ollama.model == "qwen2.5-coder:14b"
    assert ollama.base_url == "http://ollama.internal:11434"
    assert openai.model == "gpt-5"
    assert openai.base_url == "https://openai.example"
    assert openai.max_retries == 5
    assert anthropic.model == "claude-3-5-sonnet-latest"


def test_factory_rejects_unknown_provider() -> None:
    settings = Settings(model_fallback_order=("openai", "unknown"))

    with pytest.raises(ValueError, match="unknown provider"):
        build_model_gateway(settings)
