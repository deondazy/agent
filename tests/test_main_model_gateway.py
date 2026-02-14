from denosysbot.core.config import Settings
from denosysbot.main import create_app


def test_create_app_attaches_model_gateway(monkeypatch) -> None:
    settings = Settings(model_fallback_order=("ollama", "openai"))
    monkeypatch.setattr("denosysbot.main.get_settings", lambda: settings)

    app = create_app()

    gateway = app.state.model_gateway
    assert [provider.name for provider in gateway.providers] == ["ollama", "openai"]
