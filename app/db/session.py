"""Database infrastructure, consumed by repositories and migration tooling."""

import sqlite3

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _enable_sqlite_foreign_keys(
    dbapi_connection: sqlite3.Connection, connection_record: object
) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def build_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        options = {"check_same_thread": False}
        if url.database in (None, "", ":memory:"):
            engine = create_engine(url, connect_args=options, poolclass=StaticPool)
        else:
            engine = create_engine(url, connect_args=options)
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
        return engine
    return create_engine(url, pool_pre_ping=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Repositories use factory.begin() for commit/rollback and session cleanup."""
    return sessionmaker(bind=engine, expire_on_commit=False)
