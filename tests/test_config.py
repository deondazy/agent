from denosysbot.core.config import Settings


def test_defaults_are_loaded() -> None:
    settings = Settings()
    assert settings.app_name == "denosysbot"
    assert settings.vm_provider == "disposable-vm"
