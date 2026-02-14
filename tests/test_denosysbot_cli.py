from denosysbot.cli import main


def test_denosysbot_cli_tui_command_exists(monkeypatch) -> None:
    called = {"ran": False}

    def fake_run_tui(**_kwargs):
        called["ran"] = True
        return 0

    monkeypatch.setattr("denosysbot.cli.run_tui", fake_run_tui)

    code = main(["tui"])

    assert code == 0
    assert called["ran"] is True
