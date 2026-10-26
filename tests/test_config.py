import pytest

from train_status_agent import config
from train_status_agent.config import Settings


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    """Keep the local .env file out of the tests."""
    monkeypatch.setattr(config, "load_dotenv", lambda: None)


def test_reads_the_settings_from_the_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat-id")
    assert Settings.from_env() == Settings("anthropic-key", "bot-token", "chat-id")


def test_lists_the_missing_variables(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID"):
        Settings.from_env()


def test_secrets_stay_out_of_the_repr():
    settings = Settings("anthropic-key", "bot-token", "chat-id")
    assert "anthropic-key" not in repr(settings)
    assert "bot-token" not in repr(settings)
