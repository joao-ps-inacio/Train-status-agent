"""Entry point: check the commute and send the result to Telegram."""

import argparse
import logging

import anthropic

from train_status_agent.agent import check_commute
from train_status_agent.config import Settings
from train_status_agent.telegram import TelegramClient

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = "⚠️ O agente não devolveu resposta hoje."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the commute for disruptions and send the result to Telegram.")
    parser.add_argument("--dry-run", action="store_true", help="print the message without sending it to Telegram")
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx logs every request URL at INFO, and the Telegram URL contains the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    args = parse_args()
    configure_logging()
    settings = Settings.from_env()

    status = check_commute(anthropic.Anthropic(api_key=settings.anthropic_api_key)) or FALLBACK_MESSAGE
    print(status)

    if args.dry_run:
        logger.info("Dry run: message not sent to Telegram")
        return

    TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id).send_message(status)
    logger.info("Message sent to Telegram")


if __name__ == "__main__":
    main()
