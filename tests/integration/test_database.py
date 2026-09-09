from pathlib import Path

import pytest
from sqlalchemy import text

from app.db.session import build_engine, build_session_factory


def test_sessions_commit_rollback_and_foreign_keys(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'sessions.db'}")
    factory = build_session_factory(engine)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE probe (id INTEGER PRIMARY KEY)"))
        with factory.begin() as session:
            assert session.scalar(text("PRAGMA foreign_keys")) == 1
            session.execute(text("INSERT INTO probe (id) VALUES (1)"))
        with pytest.raises(RuntimeError), factory.begin() as session:
            session.execute(text("INSERT INTO probe (id) VALUES (2)"))
            raise RuntimeError("abort transaction")
        with factory() as session:
            assert session.scalars(text("SELECT id FROM probe")).all() == [1]
    finally:
        engine.dispose()
