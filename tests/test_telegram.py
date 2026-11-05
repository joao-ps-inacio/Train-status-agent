import httpx
import pytest

from train_status_agent import telegram as telegram_module
from train_status_agent.telegram import TelegramClient, TelegramError


@pytest.fixture
def post(monkeypatch):
    """Replace httpx.post, so no test reaches Telegram. Set post.response to choose the reply."""

    class FakePost:
        def __init__(self) -> None:
            self.response = httpx.Response(200, json={"ok": True})
            self.calls: list[tuple[str, dict]] = []

        def __call__(self, url: str, **kwargs) -> httpx.Response:
            self.calls.append((url, kwargs))
            return self.response

    fake = FakePost()
    monkeypatch.setattr(telegram_module.httpx, "post", fake)
    return fake


def test_send_message_posts_the_text_to_the_configured_chat(post):
    TelegramClient("bot-token", "chat-id", timeout=5).send_message("🚇 MTS: ✅")

    url, kwargs = post.calls[0]
    assert url == "https://api.telegram.org/botbot-token/sendMessage"
    assert kwargs["json"] == {"chat_id": "chat-id", "text": "🚇 MTS: ✅"}
    assert kwargs["timeout"] == 5


def test_send_message_raises_when_telegram_rejects_the_request(post):
    post.response = httpx.Response(400, json={"ok": False, "description": "Bad Request: chat not found"})

    with pytest.raises(TelegramError, match=r"400.*chat not found"):
        TelegramClient("bot-token", "chat-id").send_message("🚇 MTS: ✅")
