"""Provider fallback gateway."""

from collections.abc import Sequence
from typing import Any

from openclaw_agent.adapters.models.base import ModelProvider, ProviderError


class ModelGateway:
    """Tries model providers in order until one succeeds."""

    def __init__(self, providers: Sequence[ModelProvider]):
        if not providers:
            raise ValueError("at least one provider is required")
        self.providers = list(providers)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        errors: list[str] = []
        for provider in self.providers:
            try:
                return provider.generate(prompt, **kwargs)
            except ProviderError as exc:
                errors.append(f"{provider.name}: {exc}")
        raise ProviderError("all providers failed: " + "; ".join(errors))
