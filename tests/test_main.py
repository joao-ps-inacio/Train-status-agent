import sys

import pytest

from train_status_agent import main as cli


class FakeTelegram:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send_message(self, text: str) -> None:
        self.sent.append(text)


@pytest.fixture
def telegram(monkeypatch):
    """Replace the Telegram client and the settings, so no test needs real credentials or sends anything."""
    fake = FakeTelegram()
    monkeypatch.setattr(cli, "TelegramClient", lambda bot_token, chat_id: fake)
    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: cls("anthropic-key", "bot-token", "chat-id")))
    return fake


def run(monkeypatch, *args: str) -> None:
    monkeypatch.setattr(sys, "argv", ["train-status-agent", *args])
    cli.main()


def fail(client):
    raise RuntimeError("API down")


def test_dry_run_prints_the_status_without_sending(monkeypatch, capsys, telegram):
    monkeypatch.setattr(cli, "check_commute", lambda client: "🚇 MTS: ✅")
    run(monkeypatch, "--dry-run")
    assert capsys.readouterr().out == "🚇 MTS: ✅\n"
    assert telegram.sent == []


def test_dry_run_prints_the_failure_without_sending(monkeypatch, capsys, telegram):
    monkeypatch.setattr(cli, "check_commute", fail)
    with pytest.raises(RuntimeError):
        run(monkeypatch, "--dry-run")
    assert "O agente falhou hoje (RuntimeError)" in capsys.readouterr().out
    assert telegram.sent == []


def test_sends_the_status_to_telegram(monkeypatch, telegram):
    monkeypatch.setattr(cli, "check_commute", lambda client: "🚇 MTS: ✅")
    run(monkeypatch)
    assert telegram.sent == ["🚇 MTS: ✅"]


def test_sends_a_failure_alert_and_reraises(monkeypatch, telegram):
    monkeypatch.setattr(cli, "check_commute", fail)
    with pytest.raises(RuntimeError):
        run(monkeypatch)
    assert telegram.sent == ["⚠️ O agente falhou hoje (RuntimeError). Vê fertagus.pt"]


def test_sends_the_fallback_when_the_agent_returns_nothing(monkeypatch, telegram):
    monkeypatch.setattr(cli, "check_commute", lambda client: "")
    run(monkeypatch)
    assert telegram.sent == [cli.FALLBACK_MESSAGE]
