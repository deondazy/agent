"""Base contracts for model providers."""

from typing import Any
from typing import Protocol


class ProviderError(RuntimeError):
    """Raised when a provider request fails."""

    def __init__(
        self,
        message: str,
        *,
        retriable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retriable = retriable
        self.status_code = status_code


class ModelProvider(Protocol):
    name: str

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a model response for a prompt."""
