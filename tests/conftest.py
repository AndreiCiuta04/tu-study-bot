from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.db.session import build_engine, build_session_factory
from app.repositories.unit_of_work import UnitOfWork


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = f"sqlite:///{tmp_path / 'study.db'}"
    monkeypatch.setenv("TUW_DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    engine = build_engine(url)
    try:
        yield engine, UnitOfWork(build_session_factory(engine))
    finally:
        engine.dispose()
