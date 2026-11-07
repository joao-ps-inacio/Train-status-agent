import sys

import pytest

from train_status_agent import main as cli
from train_status_agent.telegram import TelegramError


@pytest.fixture(autouse=True)
def no_github_output(monkeypatch):
    """CI runs these tests inside GitHub Actions, where GITHUB_OUTPUT points to a real file."""
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)


@pytest.fixture
def github_output(monkeypatch, tmp_path):
    """Act as GitHub Actions: point GITHUB_OUTPUT to a file the test can read."""
    path = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))
    return path


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


def test_a_sent_failure_alert_tells_the_workflow_not_to_send_another(monkeypatch, telegram, github_output):
    monkeypatch.setattr(cli, "check_commute", fail)
    with pytest.raises(RuntimeError):
        run(monkeypatch)
    assert github_output.read_text(encoding="utf-8") == "alert_sent=true\n"


def test_a_failed_telegram_send_leaves_the_alert_to_the_workflow(monkeypatch, telegram, github_output):
    def telegram_down(text: str) -> None:
        raise TelegramError("sendMessage failed (502): Bad Gateway")

    monkeypatch.setattr(cli, "check_commute", fail)
    monkeypatch.setattr(telegram, "send_message", telegram_down)
    with pytest.raises(TelegramError):
        run(monkeypatch)
    assert not github_output.exists()


def test_a_dry_run_failure_leaves_no_note(monkeypatch, telegram, github_output):
    monkeypatch.setattr(cli, "check_commute", fail)
    with pytest.raises(RuntimeError):
        run(monkeypatch, "--dry-run")
    assert not github_output.exists()


def test_a_successful_run_leaves_no_note(monkeypatch, telegram, github_output):
    monkeypatch.setattr(cli, "check_commute", lambda client: "🚇 MTS: ✅")
    run(monkeypatch)
    assert not github_output.exists()


def test_mark_alert_sent_never_raises(monkeypatch, tmp_path):
    # A directory can't be opened as a file, so the write fails with an OSError.
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path))
    cli.mark_alert_sent()


def test_mark_alert_sent_does_nothing_outside_github_actions():
    cli.mark_alert_sent()
