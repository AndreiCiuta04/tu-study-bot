import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from telegram import Update
from telegram.constants import ChatType

from app.integrations.telegram.formatter import format_help, format_today
from app.integrations.telegram.handlers import TelegramHandlers
from app.services.today_service import get_today_items


def test_empty_today_and_help_formatting() -> None:
    assert get_today_items() == ()
    assert format_today(get_today_items()) == "Nothing planned for today yet."
    assert format_help() == (
        "/help — Show available commands\n/today — Show today's overview"
    )
    assert format_today(("Example item",)) == "Today\n• Example item"


@pytest.mark.parametrize("command", ["help", "today"])
@pytest.mark.parametrize(
    ("user_id", "chat_type", "allowed"),
    [
        (42, ChatType.PRIVATE, True),
        (99, ChatType.PRIVATE, False),
        (None, ChatType.PRIVATE, False),
        (42, ChatType.GROUP, False),
        (42, ChatType.SUPERGROUP, False),
        (42, None, False),
    ],
)
def test_handler_access_control(command, user_id, chat_type, allowed) -> None:
    update = Mock(spec=Update)
    update.effective_user = None if user_id is None else Mock(id=user_id)
    update.effective_chat = None if chat_type is None else Mock(type=chat_type)
    update.effective_message = Mock(reply_text=AsyncMock())
    handlers = TelegramHandlers(42)
    with patch(
        "app.integrations.telegram.handlers.today_service.get_today_items",
        return_value=(),
    ) as service:
        asyncio.run(getattr(handlers, command)(update, Mock()))
    if allowed:
        expected = format_help() if command == "help" else format_today(())
        update.effective_message.reply_text.assert_awaited_once_with(expected)
    else:
        update.effective_message.reply_text.assert_not_awaited()
    if allowed and command == "today":
        service.assert_called_once_with()
    else:
        service.assert_not_called()


def test_today_formats_service_result() -> None:
    update = Mock(spec=Update)
    update.effective_user = Mock(id=42)
    update.effective_chat = Mock(type=ChatType.PRIVATE)
    update.effective_message = Mock(reply_text=AsyncMock())
    with patch(
        "app.integrations.telegram.handlers.today_service.get_today_items",
        return_value=("Service result",),
    ):
        asyncio.run(TelegramHandlers(42).today(update, Mock()))
    update.effective_message.reply_text.assert_awaited_once_with(
        "Today\n• Service result"
    )


@pytest.mark.parametrize("command", ["help", "today"])
def test_missing_message_is_ignored(command) -> None:
    update = Mock(spec=Update)
    update.effective_user = Mock(id=42)
    update.effective_chat = Mock(type=ChatType.PRIVATE)
    update.effective_message = None
    with patch(
        "app.integrations.telegram.handlers.today_service.get_today_items"
    ) as service:
        asyncio.run(getattr(TelegramHandlers(42), command)(update, Mock()))
    service.assert_not_called()
