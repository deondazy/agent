"""Google Gemini provider adapter."""

from collections.abc import Callable
from typing import Any
import os

import httpx

from denosysbot.adapters.models.base import ProviderError
from denosysbot.adapters.models.http_client import request_json_with_retries


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        base_url: str = "https://generativelanguage.googleapis.com",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        initial_backoff_seconds: float = 0.5,
        max_backoff_seconds: float = 4.0,
        http_client: httpx.Client | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.sleep_fn = sleep_fn
        self.client = http_client or httpx.Client(timeout=timeout_seconds)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        if not self.api_key:
            raise ProviderError("GEMINI_API_KEY is not configured")

        model_path = self.model if self.model.startswith("models/") else f"models/{self.model}"
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
        }
        payload.update(kwargs)

        response = request_json_with_retries(
            provider_name=self.name,
            client=self.client,
            method="POST",
            url=f"{self.base_url}/v1beta/{model_path}:generateContent",
            headers={
                "x-goog-api-key": self.api_key,
                "content-type": "application/json",
            },
            payload=payload,
            max_retries=self.max_retries,
            initial_backoff_seconds=self.initial_backoff_seconds,
            max_backoff_seconds=self.max_backoff_seconds,
            sleep_fn=self.sleep_fn,
        )

        text = _extract_gemini_text(response)
        if not text:
            raise ProviderError("gemini response did not include text output")
        return text


def _extract_gemini_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return ""

    chunks: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())

    return "\n".join(chunks).strip()
