from collections import deque
import json

import httpx
import pytest

from openclaw_agent.adapters.models.anthropic import AnthropicProvider
from openclaw_agent.adapters.models.base import ProviderError
from openclaw_agent.adapters.models.ollama import OllamaProvider
from openclaw_agent.adapters.models.openai import OpenAIProvider


def _make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_provider_calls_responses_api_and_extracts_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/responses"
        assert request.headers["authorization"] == "Bearer test-openai-key"
        payload = json.loads(request.read().decode("utf-8"))
        assert payload["model"] == "gpt-5"
        assert payload["input"] == "hello"
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "hello from openai"}],
                    }
                ]
            },
        )

    provider = OpenAIProvider(
        api_key="test-openai-key",
        model="gpt-5",
        http_client=_make_client(handler),
        max_retries=0,
        initial_backoff_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    assert provider.generate("hello") == "hello from openai"


def test_openai_provider_retries_transient_errors() -> None:
    responses = deque(
        [
            httpx.Response(503, json={"error": {"message": "overloaded"}}),
            httpx.Response(200, json={"output_text": "recovered"}),
        ]
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return responses.popleft()

    provider = OpenAIProvider(
        api_key="test-openai-key",
        model="gpt-5",
        http_client=_make_client(handler),
        max_retries=2,
        initial_backoff_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    assert provider.generate("hello") == "recovered"


def test_openai_provider_raises_on_non_retriable_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    provider = OpenAIProvider(
        api_key="test-openai-key",
        model="gpt-5",
        http_client=_make_client(handler),
        max_retries=2,
        initial_backoff_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(ProviderError, match="bad request"):
        provider.generate("hello")


def test_anthropic_provider_calls_messages_api_and_extracts_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/messages"
        assert request.headers["x-api-key"] == "test-anthropic-key"
        assert request.headers["anthropic-version"] == "2023-06-01"
        payload = json.loads(request.read().decode("utf-8"))
        assert payload["model"] == "claude-sonnet-4-5"
        assert payload["messages"] == [{"role": "user", "content": "hello"}]
        return httpx.Response(200, json={"content": [{"type": "text", "text": "hello from claude"}]})

    provider = AnthropicProvider(
        api_key="test-anthropic-key",
        model="claude-sonnet-4-5",
        http_client=_make_client(handler),
        max_retries=0,
        initial_backoff_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    assert provider.generate("hello") == "hello from claude"


def test_ollama_provider_calls_generate_api_and_extracts_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/generate"
        payload = json.loads(request.read().decode("utf-8"))
        assert payload["model"] == "llama3.2"
        assert payload["prompt"] == "hello"
        assert payload["stream"] is False
        return httpx.Response(200, json={"response": "hello from ollama", "done": True})

    provider = OllamaProvider(
        base_url="http://localhost:11434",
        model="llama3.2",
        http_client=_make_client(handler),
        max_retries=0,
        initial_backoff_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    assert provider.generate("hello") == "hello from ollama"
