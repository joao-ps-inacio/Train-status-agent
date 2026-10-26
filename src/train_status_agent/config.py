"""Settings loaded from environment variables, or from a local .env file in development."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

REQUIRED_VARS = ("ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


@dataclass(frozen=True)
class Settings:
    # repr=False keeps secrets out of logs and tracebacks.
    anthropic_api_key: str = field(repr=False)
    telegram_bot_token: str = field(repr=False)
    telegram_chat_id: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        missing = [name for name in REQUIRED_VARS if not os.environ.get(name)]
        if missing:
            raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

        return cls(
            anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
            telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
        )
