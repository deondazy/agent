"""Anthropic provider adapter scaffold."""

from collections.abc import Callable
from typing import Any
import os

import httpx

from openclaw_agent.adapters.models.base import ProviderError
from openclaw_agent.adapters.models.http_client import request_json_with_retries


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5",
        base_url: str = "https://api.anthropic.com",
        anthropic_version: str = "2023-06-01",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        initial_backoff_seconds: float = 0.5,
        max_backoff_seconds: float = 4.0,
        http_client: httpx.Client | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.anthropic_version = anthropic_version
        self.max_retries = max_retries
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.sleep_fn = sleep_fn
        self.client = http_client or httpx.Client(timeout=timeout_seconds)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        if not self.api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not configured")

        max_tokens = kwargs.pop("max_tokens", 1024)
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        payload.update(kwargs)

        response = request_json_with_retries(
            provider_name=self.name,
            client=self.client,
            method="POST",
            url=f"{self.base_url}/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": self.anthropic_version,
                "content-type": "application/json",
            },
            payload=payload,
            max_retries=self.max_retries,
            initial_backoff_seconds=self.initial_backoff_seconds,
            max_backoff_seconds=self.max_backoff_seconds,
            sleep_fn=self.sleep_fn,
            retriable_status_codes={408, 409, 425, 429, 500, 529},
        )

        text = _extract_anthropic_text(response)
        if not text:
            raise ProviderError("anthropic response did not include text output")
        return text


def _extract_anthropic_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        return ""

    chunks: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())

    return "\n".join(chunks).strip()
