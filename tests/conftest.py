from fastapi.testclient import TestClient
import pytest

from openclaw_agent.api.routes.runs import clear_run_store
from openclaw_agent.main import create_app


@pytest.fixture()
def client() -> TestClient:
    clear_run_store()
    app = create_app()
    return TestClient(app)
