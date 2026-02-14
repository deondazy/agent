"""Shared HTTP request helpers for model providers."""

from collections.abc import Callable, Iterable
from typing import Any
import time

import httpx

from openclaw_agent.adapters.models.base import ProviderError


DEFAULT_RETRIABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504, 529})


def request_json_with_retries(
    *,
    provider_name: str,
    client: httpx.Client,
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    max_retries: int,
    initial_backoff_seconds: float,
    max_backoff_seconds: float,
    sleep_fn: Callable[[float], None] | None,
    retriable_status_codes: Iterable[int] | None = None,
) -> dict[str, Any]:
    retriable_codes = set(retriable_status_codes or DEFAULT_RETRIABLE_STATUS_CODES)
    sleep = sleep_fn or time.sleep

    attempt = 0
    while True:
        try:
            response = client.request(
                method=method,
                url=url,
                headers=headers,
                json=payload,
            )
        except httpx.RequestError as exc:
            if attempt < max_retries:
                _sleep_with_backoff(
                    attempt=attempt,
                    initial_backoff_seconds=initial_backoff_seconds,
                    max_backoff_seconds=max_backoff_seconds,
                    sleep_fn=sleep,
                )
                attempt += 1
                continue
            raise ProviderError(
                f"{provider_name} request failed: {exc}",
                retriable=True,
            ) from exc

        if response.status_code >= 400:
            retriable = response.status_code in retriable_codes
            if retriable and attempt < max_retries:
                _sleep_with_backoff(
                    attempt=attempt,
                    initial_backoff_seconds=initial_backoff_seconds,
                    max_backoff_seconds=max_backoff_seconds,
                    sleep_fn=sleep,
                )
                attempt += 1
                continue

            message = _extract_error_message(response)
            raise ProviderError(
                f"{provider_name} API error ({response.status_code}): {message}",
                retriable=retriable,
                status_code=response.status_code,
            )

        try:
            decoded = response.json()
        except ValueError as exc:
            raise ProviderError(f"{provider_name} returned non-JSON response") from exc

        if not isinstance(decoded, dict):
            raise ProviderError(f"{provider_name} returned unexpected JSON payload")

        return decoded


def _sleep_with_backoff(
    *,
    attempt: int,
    initial_backoff_seconds: float,
    max_backoff_seconds: float,
    sleep_fn: Callable[[float], None],
) -> None:
    if initial_backoff_seconds <= 0:
        return
    delay = min(max_backoff_seconds, initial_backoff_seconds * (2**attempt))
    sleep_fn(delay)


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or f"HTTP {response.status_code}"

    if isinstance(payload, dict):
        nested = payload.get("error")
        if isinstance(nested, dict):
            nested_message = nested.get("message")
            if isinstance(nested_message, str) and nested_message:
                return nested_message
            nested_type = nested.get("type")
            if isinstance(nested_type, str) and nested_type:
                return nested_type
        if isinstance(nested, str) and nested:
            return nested

        message = payload.get("message")
        if isinstance(message, str) and message:
            return message

        error_type = payload.get("type")
        if isinstance(error_type, str) and error_type:
            return error_type

    return response.text.strip() or f"HTTP {response.status_code}"
