"""Telegram entrypoints: authorize, call services, and format responses."""

import asyncio
from collections.abc import Callable

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from app.entities.events import ExamOverview
from app.integrations.telegram.formatter import format_exams, format_help, format_today
from app.services import today_service


class TelegramHandlers:
    def __init__(
        self, allowed_user_id: int, get_exams: Callable[[], tuple[ExamOverview, ...]]
    ) -> None:
        self.allowed_user_id = allowed_user_id
        self._get_exams = get_exams

    def _is_allowed(self, update: Update) -> bool:
        user = update.effective_user
        chat = update.effective_chat
        return (
            user is not None
            and user.id == self.allowed_user_id
            and chat is not None
            and chat.type == ChatType.PRIVATE
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update) or update.effective_message is None:
            return
        await update.effective_message.reply_text(format_help())

    async def today(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update) or update.effective_message is None:
            return
        items = today_service.get_today_items()
        await update.effective_message.reply_text(format_today(items))

    async def exams(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update) or update.effective_message is None:
            return
        exams = await asyncio.to_thread(self._get_exams)
        for message in format_exams(exams):
            await update.effective_message.reply_text(message)
