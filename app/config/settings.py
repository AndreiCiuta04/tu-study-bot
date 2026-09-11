"""Environment configuration shared by the application and Alembic."""

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.integrations.tuwel.mapper import CourseMapping


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TUW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite:///./tuw-study-bot.db", min_length=1, repr=False
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


class TelegramSettings(Settings):
    """Required only by the Telegram process; HTTP and migrations stay independent."""

    model_config = SettingsConfigDict(hide_input_in_errors=True)

    telegram_bot_token: SecretStr = Field(min_length=1)
    allowed_telegram_user_id: int = Field(gt=0)


class TuwelSettings(Settings):
    """Only the explicit TUWEL import requires a token and course selection."""

    model_config = SettingsConfigDict(hide_input_in_errors=True)
    tuwel_token: SecretStr = Field(min_length=1)
    tuwel_courses: dict[int, CourseMapping] = Field(default_factory=dict)
