import asyncio
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, StatementError

from app.db.models import Course, Event
from app.db.session import build_session_factory
from app.entities.events import CourseData, EventData
from app.integrations.telegram.handlers import TelegramHandlers
from app.integrations.tiss.client import TissClient
from app.services.exam_service import ExamService
from app.services.sync_service import SyncService

FIXTURES = Path(__file__).parents[1] / "fixtures" / "tiss"
NOW = datetime.fromisoformat("2026-09-09T12:00:00+02:00")


def test_repeated_sync_updates_same_id_and_keeps_missing(database) -> None:
    engine, uow = database
    payload = (FIXTURES / "exam_dates.xml").read_bytes()
    status = 200

    def respond(request):
        if request.url.path.endswith("/examDates"):
            return httpx.Response(status, content=payload)
        return httpx.Response(200, content=(FIXTURES / "course.xml").read_bytes())

    async def sync():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            return await SyncService(TissClient(http), uow).sync_exams(
                "194.025", "2026S"
            )

    assert asyncio.run(sync()) == 1
    with build_session_factory(engine)() as session:
        original = session.scalar(select(Event))
        original_id, first_seen, created = (
            original.id,
            original.first_seen_at,
            original.created_at,
        )
    assert asyncio.run(sync()) == 1
    with build_session_factory(engine)() as session:
        unchanged = session.scalar(select(Event))
        assert unchanged.updated_at == created
        assert unchanged.last_seen_at >= first_seen
    payload = payload.replace(b"2026-09-09T10:00", b"2026-09-10T11:00")
    payload = payload.replace(b"Exam 2nd Attempt", b"Updated exam")
    assert asyncio.run(sync()) == 1
    with build_session_factory(engine)() as session:
        assert session.scalar(select(func.count()).select_from(Course)) == 1
        assert session.scalar(select(func.count()).select_from(Event)) == 1
        event = session.scalar(select(Event))
        assert event.id == original_id
        assert event.first_seen_at == first_seen
        assert event.created_at == created
        assert event.last_seen_at >= first_seen
        assert event.updated_at > created
        assert event.starts_at.day == 10
        assert event.starts_at.hour == 11
        assert str(event.starts_at.tzinfo) == "Europe/Vienna"
        assert event.title.startswith("Updated exam")
    status = 404
    assert asyncio.run(sync()) == 0
    assert len(ExamService(uow).upcoming(NOW)) == 1


@pytest.mark.parametrize("failure", ["server", "parse", "network", "invalid_course"])
def test_failed_sync_preserves_database(database, failure) -> None:
    engine, uow = database
    with uow.transaction() as repos:
        course_id = repos.courses.upsert(CourseData("194025", "2026S", "Original"), NOW)
        repos.events.upsert(
            course_id, EventData("Original", NOW, "tiss", "original"), NOW
        )

    def respond(request):
        if failure == "invalid_course" and not request.url.path.endswith("/examDates"):
            return httpx.Response(404)
        if request.url.path.endswith("/examDates"):
            if failure == "network":
                raise httpx.ConnectError("offline")
            return httpx.Response(
                500 if failure == "server" else 200, content=b"<html/>"
            )
        return httpx.Response(200, content=(FIXTURES / "course.xml").read_bytes())

    async def sync():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            await SyncService(TissClient(http), uow).sync_exams("194025", "2026S")

    with pytest.raises((httpx.HTTPError, ValueError)):
        asyncio.run(sync())
    with build_session_factory(engine)() as session:
        assert session.scalar(select(Course.name)) == "Original"
        assert session.scalar(select(func.count()).select_from(Event)) == 1


def test_repository_queries_and_atomic_rollback(database) -> None:
    engine, uow = database
    with uow.transaction() as repos:
        course = CourseData("194025", "2026S", "Machine Learning")
        course_id = repos.courses.upsert(course, NOW)
        assert repos.courses.upsert(replace(course, name="Updated"), NOW) == course_id
        assert repos.courses.upsert(replace(course, semester="2026W"), NOW) != course_id
        for source_id, offset, kind in [
            ("past", -1, "exam"),
            ("today", 0, "exam"),
            ("future", 1, "exam"),
            ("other", 1, "other"),
        ]:
            repos.events.upsert(
                course_id,
                EventData(
                    source_id,
                    NOW + timedelta(days=offset),
                    "tiss",
                    source_id,
                    event_type=kind,
                ),
                NOW,
            )
    exams = ExamService(uow).upcoming(NOW + timedelta(hours=5))
    assert [e.exam.title for e in exams] == ["today", "future"]
    assert [e.days_remaining for e in exams] == [0, 1]
    assert all(e.exam.course_name == "Updated" for e in exams)
    with pytest.raises(IntegrityError), uow.transaction() as repos:
        new_id = repos.courses.upsert(CourseData("000001", "2026S", "Rollback"), NOW)
        repos.events.upsert(new_id + 1000, EventData("Bad FK", NOW, "tiss", "bad"), NOW)
    with build_session_factory(engine)() as session:
        assert session.scalar(select(func.count()).select_from(Course)) == 2


def test_unique_source_identity_and_naive_time_rejection(database) -> None:
    engine, uow = database
    with uow.transaction() as repos:
        course_id = repos.courses.upsert(CourseData("194025", "2026S", "ML"), NOW)
        repos.events.upsert(course_id, EventData("Exam", NOW, "tiss", "1"), NOW)
    factory = build_session_factory(engine)
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.add(
            Event(
                course_id=course_id,
                event_type="exam",
                title="Duplicate",
                starts_at=NOW,
                source="tiss",
                source_id="1",
                first_seen_at=NOW,
                last_seen_at=NOW,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    with (
        pytest.raises(StatementError, match="timezone-aware"),
        uow.transaction() as repos,
    ):
        repos.events.upsert(
            course_id, EventData("Naive", datetime(2026, 1, 1), "tiss", "2"), NOW
        )


def test_exams_handler_against_persisted_data(database) -> None:
    _, uow = database
    service = ExamService(uow)
    update = Mock()
    update.effective_user.id = 42
    update.effective_chat.type = "private"
    update.effective_message.reply_text = AsyncMock()
    handlers = TelegramHandlers(
        42, lambda: service.upcoming(NOW), Mock(return_value=()), Mock(return_value=())
    )
    asyncio.run(handlers.exams(update, Mock()))
    update.effective_message.reply_text.assert_awaited_once_with(
        "No upcoming exams found."
    )
    update.effective_message.reply_text.reset_mock()
    with uow.transaction() as repos:
        cid = repos.courses.upsert(
            CourseData("194025", "2026S", "Machine Learning"), NOW
        )
        repos.events.upsert(
            cid, EventData("Final exam", NOW + timedelta(days=19), "tiss", "1"), NOW
        )
    asyncio.run(handlers.exams(update, Mock()))
    update.effective_message.reply_text.assert_awaited_once_with(
        "📚 Upcoming exams\n\nMachine Learning\nFinal exam\n28 Sep 2026 — D-19"
    )


def test_head_matches_metadata_and_downgrades(database) -> None:
    engine, _ = database
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    command.check(config)
    command.downgrade(config, "0001_foundation")
    from sqlalchemy import inspect

    assert inspect(engine).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    assert set(inspect(engine).get_table_names()) == {
        "alembic_version",
        "courses",
        "events",
    }
