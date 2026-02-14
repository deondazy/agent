import pytest

from openclaw_agent.adapters.models.base import ProviderError
from openclaw_agent.adapters.models.gateway import ModelGateway


class FailingProvider:
    name = "failing"

    def generate(self, prompt: str, **kwargs: str) -> str:
        raise ProviderError("boom")


class WorkingProvider:
    name = "working"

    def generate(self, prompt: str, **kwargs: str) -> str:
        return "fallback-response"


def test_gateway_falls_back_when_primary_fails() -> None:
    gateway = ModelGateway([FailingProvider(), WorkingProvider()])

    result = gateway.generate("build a plan")

    assert result == "fallback-response"


def test_gateway_raises_if_all_providers_fail() -> None:
    gateway = ModelGateway([FailingProvider()])

    with pytest.raises(ProviderError):
        gateway.generate("build a plan")
