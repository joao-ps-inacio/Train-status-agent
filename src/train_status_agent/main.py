"""Entry point: check the commute and send the result to Telegram."""

import argparse
import logging

import anthropic

from train_status_agent.agent import check_commute
from train_status_agent.config import Settings
from train_status_agent.telegram import TelegramClient

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = "⚠️ O agente não devolveu resposta hoje."

# The SDK default is 10 minutes per attempt, with 2 retries. Three attempts at this
# value stay under the workflow's 8-minute step limit, so the except below gets to run.
API_TIMEOUT_SECONDS = 120


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the commute for disruptions and send the result to Telegram.")
    parser.add_argument("--dry-run", action="store_true", help="print the message without sending it to Telegram")
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx and httpx2 (used by the anthropic SDK) log every request URL at INFO,
    # and the Telegram URL contains the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)


def main() -> None:
    args = parse_args()
    configure_logging()
    settings = Settings.from_env()
    telegram = TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id)

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=API_TIMEOUT_SECONDS)
        status = check_commute(client) or FALLBACK_MESSAGE
    except Exception as error:
        logger.exception("An error occurred while checking the commute")
        message = f"⚠️ O agente falhou hoje ({type(error).__name__}). Vê fertagus.pt"
        if args.dry_run:
            print(message)
        else:
            telegram.send_message(message)
        raise

    if args.dry_run:
        print(status)
        return

    logger.info("Sending to Telegram: %s", status)
    telegram.send_message(status)
    logger.info("Message sent to Telegram")
