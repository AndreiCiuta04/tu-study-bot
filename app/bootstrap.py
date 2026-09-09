"""Composition root: connect infrastructure to services outside entrypoints."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

import httpx

from app.db.session import build_engine, build_session_factory
from app.entities.events import ExamOverview
from app.integrations.tiss.client import TissClient
from app.repositories.unit_of_work import UnitOfWork
from app.services.exam_service import ExamService
from app.services.sync_service import SyncService


@contextmanager
def exam_service(database_url: str) -> Iterator[ExamService]:
    engine = build_engine(database_url)
    try:
        yield ExamService(UnitOfWork(build_session_factory(engine)))
    finally:
        engine.dispose()


async def sync_tiss(
    database_url: str, course: str, semester: str, from_date: date | None = None
) -> int:
    engine = build_engine(database_url)
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            service = SyncService(
                TissClient(http), UnitOfWork(build_session_factory(engine))
            )
            return await service.sync_exams(course, semester, from_date)
    finally:
        engine.dispose()


def load_exams(database_url: str) -> tuple[ExamOverview, ...]:
    with exam_service(database_url) as service:
        return service.upcoming()
