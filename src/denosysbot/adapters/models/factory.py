"""Runtime factory for model providers and gateway wiring."""

from denosysbot.adapters.models.anthropic import AnthropicProvider
from denosysbot.adapters.models.gateway import ModelGateway
from denosysbot.adapters.models.gemini import GeminiProvider
from denosysbot.adapters.models.ollama import OllamaProvider
from denosysbot.adapters.models.openai import OpenAIProvider
from denosysbot.core.config import Settings


def build_model_gateway(settings: Settings) -> ModelGateway:
    """Build a provider-ordered gateway from runtime settings."""

    providers = []
    for provider_name in settings.model_fallback_order:
        normalized = provider_name.strip().lower()

        if normalized == "openai":
            providers.append(
                OpenAIProvider(
                    model=settings.model_openai_model,
                    base_url=settings.model_openai_base_url,
                    timeout_seconds=settings.model_openai_timeout_seconds,
                    max_retries=settings.model_openai_max_retries,
                    initial_backoff_seconds=settings.model_openai_initial_backoff_seconds,
                    max_backoff_seconds=settings.model_openai_max_backoff_seconds,
                )
            )
            continue

        if normalized == "anthropic":
            providers.append(
                AnthropicProvider(
                    model=settings.model_anthropic_model,
                    base_url=settings.model_anthropic_base_url,
                    anthropic_version=settings.model_anthropic_version,
                    timeout_seconds=settings.model_anthropic_timeout_seconds,
                    max_retries=settings.model_anthropic_max_retries,
                    initial_backoff_seconds=settings.model_anthropic_initial_backoff_seconds,
                    max_backoff_seconds=settings.model_anthropic_max_backoff_seconds,
                )
            )
            continue

        if normalized == "ollama":
            providers.append(
                OllamaProvider(
                    model=settings.model_ollama_model,
                    base_url=settings.model_ollama_base_url,
                    timeout_seconds=settings.model_ollama_timeout_seconds,
                    max_retries=settings.model_ollama_max_retries,
                    initial_backoff_seconds=settings.model_ollama_initial_backoff_seconds,
                    max_backoff_seconds=settings.model_ollama_max_backoff_seconds,
                )
            )
            continue

        if normalized == "gemini":
            providers.append(
                GeminiProvider(
                    model=settings.model_gemini_model,
                    base_url=settings.model_gemini_base_url,
                    timeout_seconds=settings.model_gemini_timeout_seconds,
                    max_retries=settings.model_gemini_max_retries,
                    initial_backoff_seconds=settings.model_gemini_initial_backoff_seconds,
                    max_backoff_seconds=settings.model_gemini_max_backoff_seconds,
                )
            )
            continue

        raise ValueError(f"unknown provider in model_fallback_order: {provider_name}")

    return ModelGateway(providers)
