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
        "/help — Show available commands\n"
        "/today — Show today's overview\n/exams — Show upcoming exams\n"
        "/deadlines — Show upcoming deadlines\n/week — Show the next 7 days"
    )
    assert format_today(("Example item",)) == "Today\n• Example item"


@pytest.mark.parametrize("command", ["help", "today", "exams", "deadlines", "week"])
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
    exam_service = Mock(return_value=())
    deadline_service = Mock(return_value=())
    week_service = Mock(return_value=())
    handlers = TelegramHandlers(42, exam_service, deadline_service, week_service)
    with patch(
        "app.integrations.telegram.handlers.today_service.get_today_items",
        return_value=(),
    ) as service:
        asyncio.run(getattr(handlers, command)(update, Mock()))
    if allowed:
        expected = {
            "help": format_help(),
            "today": format_today(()),
            "exams": "No upcoming exams found.",
            "deadlines": "No upcoming deadlines found.",
            "week": "No events in the next 7 days.",
        }[command]
        update.effective_message.reply_text.assert_awaited_once_with(expected)
    else:
        update.effective_message.reply_text.assert_not_awaited()
    if allowed and command == "exams":
        exam_service.assert_called_once_with()
    else:
        exam_service.assert_not_called()
    for name, callback in [("deadlines", deadline_service), ("week", week_service)]:
        if allowed and command == name:
            callback.assert_called_once_with()
        else:
            callback.assert_not_called()
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
        asyncio.run(
            TelegramHandlers(
                42, Mock(return_value=()), Mock(return_value=()), Mock(return_value=())
            ).today(update, Mock())
        )
    update.effective_message.reply_text.assert_awaited_once_with(
        "Today\n• Service result"
    )


@pytest.mark.parametrize("command", ["help", "today", "exams", "deadlines", "week"])
def test_missing_message_is_ignored(command) -> None:
    update = Mock(spec=Update)
    update.effective_user = Mock(id=42)
    update.effective_chat = Mock(type=ChatType.PRIVATE)
    update.effective_message = None
    with patch(
        "app.integrations.telegram.handlers.today_service.get_today_items"
    ) as service:
        asyncio.run(
            getattr(
                TelegramHandlers(
                    42,
                    Mock(return_value=()),
                    Mock(return_value=()),
                    Mock(return_value=()),
                ),
                command,
            )(update, Mock())
        )
    service.assert_not_called()


def test_exam_formatting_today_and_long_responses() -> None:
    from datetime import datetime

    from app.entities.events import Exam, ExamOverview
    from app.integrations.telegram.formatter import format_exams

    exam = Exam(
        1, "Course", "Exam", datetime.fromisoformat("2027-01-09T10:00:00+01:00"), None
    )
    assert format_exams((ExamOverview(exam, 0),)) == (
        "📚 Upcoming exams\n\nCourse\nExam\n9 Jan 2027 — Today",
    )
    long_exam = Exam(2, "😀" * 500, "T" * 500, exam.starts_at, None)
    messages = format_exams((ExamOverview(long_exam, 1),) * 10)
    assert len(messages) > 1
    assert all(len(message.encode("utf-16-le")) // 2 <= 4096 for message in messages)
    assert sum(message.count("D-1") for message in messages) == 10
