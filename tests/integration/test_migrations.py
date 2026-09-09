from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.db.session import build_engine

ROOT = Path(__file__).resolve().parents[2]


def test_baseline_upgrade_downgrade_and_reupgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("TUW_DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    engine = build_engine(url)
    try:
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert inspect(connection).get_table_names() == ["alembic_version"]
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0001_foundation"
            )
        command.downgrade(config, "base")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT COUNT(*) FROM alembic_version")) == 0
        command.upgrade(config, "head")
        command.check(config)
    finally:
        engine.dispose()
