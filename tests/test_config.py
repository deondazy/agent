from openclaw_agent.core.config import Settings


def test_defaults_are_loaded() -> None:
    settings = Settings()
    assert settings.app_name == "openclaw-agent"
    assert settings.vm_provider == "disposable-vm"
