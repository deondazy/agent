"""OpenAI provider adapter scaffold."""

from typing import Any
from collections.abc import Callable
import os

import httpx

from openclaw_agent.adapters.models.base import ProviderError
from openclaw_agent.adapters.models.http_client import request_json_with_retries


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4.1",
        base_url: str = "https://api.openai.com",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        initial_backoff_seconds: float = 0.5,
        max_backoff_seconds: float = 4.0,
        http_client: httpx.Client | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.sleep_fn = sleep_fn
        self.client = http_client or httpx.Client(timeout=timeout_seconds)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is not configured")

        payload = {"model": self.model, "input": prompt}
        payload.update(kwargs)

        response = request_json_with_retries(
            provider_name=self.name,
            client=self.client,
            method="POST",
            url=f"{self.base_url}/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload=payload,
            max_retries=self.max_retries,
            initial_backoff_seconds=self.initial_backoff_seconds,
            max_backoff_seconds=self.max_backoff_seconds,
            sleep_fn=self.sleep_fn,
        )
        text = _extract_openai_text(response)
        if not text:
            raise ProviderError("openai response did not include text output")
        return text


def _extract_openai_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    chunks: list[str] = []
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    text = block.get("text")
                    block_type = block.get("type")
                    if isinstance(text, str) and block_type in {"output_text", "text"}:
                        chunks.append(text)
            text = item.get("text")
            if isinstance(text, str):
                chunks.append(text)

    return "\n".join(chunk.strip() for chunk in chunks if chunk and chunk.strip()).strip()
