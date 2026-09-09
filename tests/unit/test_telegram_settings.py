import pytest
from pydantic import ValidationError

from app.config.settings import Settings, TelegramSettings


@pytest.fixture(autouse=True)
def clean_telegram_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TUW_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TUW_ALLOWED_TELEGRAM_USER_ID", raising=False)


def test_http_settings_need_no_telegram_credentials() -> None:
    Settings(_env_file=None)


def test_telegram_requires_credentials() -> None:
    with pytest.raises(ValidationError):
        TelegramSettings(_env_file=None)


def test_telegram_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TUW_TELEGRAM_BOT_TOKEN", "123:TEST_ONLY")
    monkeypatch.setenv("TUW_ALLOWED_TELEGRAM_USER_ID", "42")
    settings = TelegramSettings(_env_file=None)
    assert settings.telegram_bot_token.get_secret_value() == "123:TEST_ONLY"
    assert settings.allowed_telegram_user_id == 42
    assert "TEST_ONLY" not in repr(settings)
    assert "TEST_ONLY" not in settings.model_dump_json()


@pytest.mark.parametrize("user_id", ["0", "-1", "not-a-number"])
def test_invalid_user_id(monkeypatch: pytest.MonkeyPatch, user_id: str) -> None:
    monkeypatch.setenv("TUW_TELEGRAM_BOT_TOKEN", "123:TEST_ONLY")
    monkeypatch.setenv("TUW_ALLOWED_TELEGRAM_USER_ID", user_id)
    with pytest.raises(ValidationError) as error:
        TelegramSettings(_env_file=None)
    assert "TEST_ONLY" not in str(error.value)


def test_empty_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TUW_TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TUW_ALLOWED_TELEGRAM_USER_ID", "42")
    with pytest.raises(ValidationError):
        TelegramSettings(_env_file=None)
