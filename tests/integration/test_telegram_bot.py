import asyncio
import json
from unittest.mock import Mock, patch

import pytest
from pydantic import SecretStr
from telegram import Update
from telegram.request import HTTPXRequest

from app.config.settings import TelegramSettings
from app.integrations.telegram.bot import build_application, handle_error, main


def test_initialization_and_command_dispatch() -> None:
    replies = []

    async def request(self, url, method, request_data=None, **kwargs):
        if url.endswith("/getMe"):
            result = {
                "id": 123,
                "is_bot": True,
                "first_name": "Test",
                "username": "test_bot",
            }
        elif url.endswith("/sendMessage"):
            replies.append(request_data.parameters["text"])
            result = {
                "message_id": 2,
                "date": 0,
                "chat": {"id": 42, "type": "private"},
                "text": request_data.parameters["text"],
            }
        else:
            pytest.fail("Unexpected Telegram API call")
        return 200, json.dumps({"ok": True, "result": result}).encode()

    async def exercise() -> None:
        settings = TelegramSettings(
            _env_file=None,
            telegram_bot_token=SecretStr("123:TEST_ONLY"),
            allowed_telegram_user_id=42,
            database_url="sqlite:///:memory:",
        )
        application = build_application(settings)
        with patch.object(HTTPXRequest, "do_request", request):
            async with application:
                for command, user_id in [
                    ("/help", 42),
                    ("/today", 42),
                    ("/help", 99),
                    ("/today", 99),
                ]:
                    update = Update.de_json(
                        {
                            "update_id": 1,
                            "message": {
                                "message_id": 1,
                                "date": 0,
                                "chat": {"id": user_id, "type": "private"},
                                "from": {
                                    "id": user_id,
                                    "is_bot": False,
                                    "first_name": "Test",
                                },
                                "text": command,
                                "entities": [
                                    {
                                        "type": "bot_command",
                                        "offset": 0,
                                        "length": len(command),
                                    }
                                ],
                            },
                        },
                        application.bot,
                    )
                    await application.process_update(update)

    asyncio.run(exercise())
    assert replies == [
        "/help — Show available commands\n/today — Show today's overview",
        "Nothing planned for today yet.",
    ]


def test_startup_runs_polling_without_network() -> None:
    with (
        patch("app.integrations.telegram.bot.TelegramSettings") as settings,
        patch("app.integrations.telegram.bot.configure_logging"),
        patch("app.integrations.telegram.bot.build_application") as build,
    ):
        main()
    build.assert_called_once_with(settings.return_value)
    build.return_value.run_polling.assert_called_once_with(allowed_updates=["message"])


def test_error_logging_does_not_expose_payload_or_secret(caplog) -> None:
    context = Mock(error=RuntimeError("123:TEST_ONLY"))
    asyncio.run(handle_error({"private": "payload"}, context))
    assert "RuntimeError" in caplog.text
    assert "TEST_ONLY" not in caplog.text
    assert "payload" not in caplog.text
