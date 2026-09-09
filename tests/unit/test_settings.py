from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TUW_DATABASE_URL", raising=False)
    monkeypatch.delenv("TUW_LOG_LEVEL", raising=False)


def test_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite:///./tuw-study-bot.db"
    assert settings.log_level == "INFO"


def test_environment_overrides_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "TUW_DATABASE_URL=sqlite:///file.db\nTUW_LOG_LEVEL=WARNING\n"
    )
    assert Settings().database_url == "sqlite:///file.db"
    monkeypatch.setenv("TUW_DATABASE_URL", "sqlite:///environment.db")
    assert Settings().database_url == "sqlite:///environment.db"
    assert Settings().log_level == "WARNING"


@pytest.mark.parametrize(
    ("name", "value"), [("TUW_LOG_LEVEL", "invalid"), ("TUW_DATABASE_URL", "")]
)
def test_invalid_settings(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_database_credentials_not_in_repr() -> None:
    settings = Settings(database_url="postgresql://user:secret@localhost/db")
    assert "secret" not in repr(settings)
