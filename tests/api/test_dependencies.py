from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from denosysbot.adapters.models.gateway import ModelGateway
from denosysbot.api.dependencies import get_model_gateway


class DummyProvider:
    name = "dummy"

    def generate(self, prompt: str, **kwargs: str) -> str:
        return "ok"


def _build_app(with_gateway: bool) -> FastAPI:
    app = FastAPI()
    if with_gateway:
        app.state.model_gateway = ModelGateway([DummyProvider()])

    @app.get("/gateway")
    def gateway_info(gateway: ModelGateway = Depends(get_model_gateway)) -> dict[str, list[str]]:
        return {"providers": [provider.name for provider in gateway.providers]}

    return app


def test_get_model_gateway_dependency_resolves_from_app_state() -> None:
    client = TestClient(_build_app(with_gateway=True))

    response = client.get("/gateway")

    assert response.status_code == 200
    assert response.json() == {"providers": ["dummy"]}


def test_get_model_gateway_dependency_returns_500_when_missing() -> None:
    client = TestClient(_build_app(with_gateway=False))

    response = client.get("/gateway")

    assert response.status_code == 500
    assert response.json() == {"detail": "model_gateway_unavailable"}
