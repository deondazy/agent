"""Ollama provider adapter scaffold."""

from collections.abc import Callable
from typing import Any
import os

import httpx

from denosysbot.adapters.models.base import ProviderError
from denosysbot.adapters.models.http_client import request_json_with_retries


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        api_key: str | None = None,
        timeout_seconds: float = 90.0,
        max_retries: int = 2,
        initial_backoff_seconds: float = 0.5,
        max_backoff_seconds: float = 4.0,
        http_client: httpx.Client | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ):
        self.base_url = base_url
        self.model = model
        self.api_key = api_key or os.getenv("OLLAMA_API_KEY")
        self.max_retries = max_retries
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.sleep_fn = sleep_fn
        self.client = http_client or httpx.Client(timeout=timeout_seconds)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        payload.update(kwargs)

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = request_json_with_retries(
            provider_name=self.name,
            client=self.client,
            method="POST",
            url=f"{self.base_url.rstrip('/')}/api/generate",
            headers=headers,
            payload=payload,
            max_retries=self.max_retries,
            initial_backoff_seconds=self.initial_backoff_seconds,
            max_backoff_seconds=self.max_backoff_seconds,
            sleep_fn=self.sleep_fn,
        )

        text = response.get("response")
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("ollama response did not include text output")
        return text.strip()
