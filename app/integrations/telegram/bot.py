"""Run with python -m app.integrations.telegram.bot."""

import logging
from functools import partial
from typing import Any

from telegram.ext import Application, CommandHandler, ContextTypes

from app.bootstrap import load_exams
from app.config.logging import configure_logging
from app.config.settings import TelegramSettings
from app.integrations.telegram.handlers import TelegramHandlers

logger = logging.getLogger(__name__)


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Exception text and update payloads can contain credentials or personal data.
    logger.error("Telegram update failed (%s)", type(context.error).__name__)


def build_application(
    settings: TelegramSettings,
) -> Application[Any, Any, Any, Any, Any, Any]:
    handlers = TelegramHandlers(
        settings.allowed_telegram_user_id, partial(load_exams, settings.database_url)
    )
    application = (
        Application.builder()
        .token(settings.telegram_bot_token.get_secret_value())
        .build()
    )
    application.add_handler(CommandHandler("help", handlers.help))
    application.add_handler(CommandHandler("today", handlers.today))
    application.add_handler(CommandHandler("exams", handlers.exams))
    application.add_error_handler(handle_error)
    return application


def main() -> None:
    settings = TelegramSettings()
    configure_logging(settings.log_level)
    # HTTP debug/request logs include the bot token in the request URL.
    for name in ("httpx", "httpcore", "telegram"):
        logging.getLogger(name).setLevel(logging.WARNING)
    application = build_application(settings)
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
