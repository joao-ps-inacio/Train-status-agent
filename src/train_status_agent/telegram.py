"""Minimal client for the Telegram Bot API."""

import httpx

API_URL = "https://api.telegram.org/bot{token}/{method}"


class TelegramError(RuntimeError):
    """Raised when the Telegram Bot API rejects a request."""


class TelegramClient:
    def __init__(self, bot_token: str, chat_id: str, timeout: float = 30) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._timeout = timeout

    def send_message(self, text: str) -> None:
        """Send a text message to the configured chat."""
        url = API_URL.format(token=self._bot_token, method="sendMessage")
        response = httpx.post(url, json={"chat_id": self._chat_id, "text": text}, timeout=self._timeout)

        payload = response.json()
        if not payload.get("ok"):
            raise TelegramError(f"sendMessage failed ({response.status_code}): {payload.get('description')}")
