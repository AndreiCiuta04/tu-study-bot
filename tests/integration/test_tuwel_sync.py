import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app.db.models import Course, Event
from app.db.session import build_session_factory
from app.entities.events import CourseData, EventData
from app.integrations.telegram.handlers import TelegramHandlers
from app.integrations.tuwel.auth import TokenAuth
from app.integrations.tuwel.client import TuwelClient
from app.integrations.tuwel.errors import TuwelAuthenticationError, TuwelError
from app.integrations.tuwel.mapper import CourseMapping
from app.services.event_service import EventService
from app.services.exam_service import ExamService
from app.services.tuwel_sync_service import TuwelSyncService

FIXTURES = Path(__file__).parents[1] / "fixtures" / "tuwel"
NOW = datetime.fromisoformat("2026-10-09T12:00:00+02:00")
MAPPING = {101: CourseMapping(course_code="194025", semester="2026S")}
FUNCTIONS = {
    "core_webservice_get_site_info": "site",
    "core_enrol_get_users_courses": "courses",
    "mod_assign_get_assignments": "assignments",
    "core_calendar_get_calendar_events": "calendar",
    "mod_assign_get_submission_status": "submission",
}


def responses():
    return {
        function: json.loads((FIXTURES / f"{name}.json").read_text())
        for function, name in FUNCTIONS.items()
    }


def synchronize(uow, payloads, mappings=MAPPING, now=NOW):
    def respond(request):
        params = parse_qs(request.content.decode())
        function = params["wsfunction"][0]
        assert "TEST_TOKEN" not in str(request.url)
        assert params["moodlewsrestformat"] == ["json"]
        if function == "core_enrol_get_users_courses":
            assert params["userid"] == ["42"]
        if function == "mod_assign_get_submission_status":
            assert params["assignid"] == ["501"]
            assert params["userid"] == ["0"]
        if function == "mod_assign_get_assignments":
            assert params["courseids[0]"] == ["101"]
        if function == "core_calendar_get_calendar_events":
            assert params["events[courseids][0]"] == ["101"]
            assert int(params["options[timeend]"][0]) > int(
                params["options[timestart]"][0]
            )
        return httpx.Response(200, json=payloads[function])

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            return await TuwelSyncService(
                TuwelClient(http, TokenAuth(SecretStr("TEST_TOKEN"))), uow
            ).sync(mappings, now)

    return asyncio.run(call())


def seed_tiss(uow):
    with uow.transaction() as repos:
        cid = repos.courses.upsert(
            CourseData("194025", "2026S", "Machine Learning"), NOW
        )
        repos.events.upsert(
            cid, EventData("TISS exam", NOW + timedelta(days=2), "tiss", "528535"), NOW
        )


def test_atomic_idempotent_sync_due_updates_and_shared_course(database) -> None:
    engine, uow = database
    seed_tiss(uow)
    payloads = responses()
    assert synchronize(uow, payloads) == 2
    with build_session_factory(engine)() as session:
        original = session.scalar(select(Event).where(Event.source_id == "assign:501"))
        original_id, first_seen, created, updated = (
            original.id,
            original.first_seen_at,
            original.created_at,
            original.updated_at,
        )
        assert original.submission_status == "submitted"
        assert original.source_url.endswith("/mod/assign/view.php?id=601")
        assert session.scalar(select(func.count()).select_from(Course)) == 1
        assert session.scalar(select(func.count()).select_from(Event)) == 3
        due = original.due_at
    assert synchronize(uow, payloads, now=NOW + timedelta(hours=1)) == 2
    with build_session_factory(engine)() as session:
        event = session.get(Event, original_id)
        assert event.updated_at == updated
        assert event.last_seen_at > first_seen
    # The old calendar copy must not override the activity's changed effective due date.
    payloads["mod_assign_get_assignments"]["courses"][0]["assignments"][0][
        "duedate"
    ] += 86400
    assert synchronize(uow, payloads, now=NOW + timedelta(hours=2)) == 2
    with build_session_factory(engine)() as session:
        event = session.get(Event, original_id)
        assert event.due_at == due + timedelta(days=1)
        assert event.created_at == created
        assert event.first_seen_at == first_seen
        assert event.updated_at > updated
        assert session.scalar(select(func.count()).select_from(Event)) == 3
    assert len(ExamService(uow).upcoming(NOW)) == 1


@pytest.mark.parametrize("failure", ["auth", "malformed", "warnings"])
def test_failed_sync_preserves_both_sources(database, failure) -> None:
    engine, uow = database
    seed_tiss(uow)
    payloads = responses()
    synchronize(uow, payloads)
    payloads["mod_assign_get_submission_status"] = {
        "auth": {"errorcode": "invalidtoken", "exception": "moodle_exception"},
        "malformed": {"lastattempt": {"submission": {"status": None}}},
        "warnings": {"warnings": [{"message": "Unavailable"}]},
    }[failure]
    with pytest.raises(TuwelAuthenticationError if failure == "auth" else TuwelError):
        synchronize(uow, payloads, now=NOW + timedelta(days=1))
    with build_session_factory(engine)() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 3
        for event in session.scalars(select(Event)):
            assert event.last_seen_at == NOW
    assert len(ExamService(uow).upcoming(NOW)) == 1


def test_empty_results_and_unavailable_submission_do_not_delete(database) -> None:
    engine, uow = database
    payloads = responses()
    payloads["core_webservice_get_site_info"]["functions"] = [
        item
        for item in payloads["core_webservice_get_site_info"]["functions"]
        if item["name"] != "mod_assign_get_submission_status"
    ]
    synchronize(uow, payloads)
    with build_session_factory(engine)() as session:
        assert (
            session.scalar(
                select(Event.submission_status).where(Event.source_id == "assign:501")
            )
            is None
        )
    payloads["mod_assign_get_assignments"] = {"courses": [], "warnings": []}
    payloads["core_calendar_get_calendar_events"] = {"events": [], "warnings": []}
    assert synchronize(uow, payloads) == 0
    with build_session_factory(engine)() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 2
    payloads["core_enrol_get_users_courses"] = []
    assert synchronize(uow, payloads, mappings={}) == 0


def test_calendar_only_assignment_later_activity_is_same_record(database) -> None:
    engine, uow = database
    payloads = responses()
    original_assignments = payloads["mod_assign_get_assignments"]
    payloads["mod_assign_get_assignments"] = {"courses": [], "warnings": []}
    synchronize(uow, payloads)
    with build_session_factory(engine)() as session:
        original_id = session.scalar(
            select(Event.id).where(Event.source_id == "assign:501")
        )
    payloads["mod_assign_get_assignments"] = original_assignments
    synchronize(uow, payloads)
    with build_session_factory(engine)() as session:
        assert (
            session.scalar(select(Event.id).where(Event.source_id == "assign:501"))
            == original_id
        )
        assert session.scalar(select(func.count()).select_from(Event)) == 2


def test_mapping_failure_opens_no_transaction() -> None:
    payloads = responses()
    uow = MagicMock()
    with pytest.raises(ValueError, match="Configure"):
        synchronize(uow, payloads, mappings={})
    uow.transaction.assert_not_called()


def test_week_and_deadlines_against_persisted_mixed_data(database) -> None:
    _, uow = database
    seed_tiss(uow)
    synchronize(uow, responses())
    service = EventService(uow)
    deadlines = service.overview(now=NOW)
    assert len(deadlines) == 2
    week = service.overview(week=True, now=NOW)
    assert len({item.event.id for item in week}) == len(week)
    assert {item.event.source for item in week} == {"tiss", "tuwel"}
    update = Mock()
    update.effective_user.id = 42
    update.effective_chat.type = "private"
    update.effective_message.reply_text = AsyncMock()
    handler = TelegramHandlers(
        42,
        lambda: ExamService(uow).upcoming(NOW),
        lambda: service.overview(now=NOW),
        lambda: service.overview(week=True, now=NOW),
    )
    asyncio.run(handler.deadlines(update, Mock()))
    text = update.effective_message.reply_text.call_args.args[0]
    assert text.startswith("📌 Upcoming deadlines")
    assert text.count("Assignment 2") == 1
    assert "submitted" in text
    assert "TISS exam" not in text
    asyncio.run(handler.week(update, Mock()))
    text = update.effective_message.reply_text.call_args.args[0]
    assert "📅 Next 7 days" in text
    assert "TISS exam" in text
    assert text.count("Assignment 2") == 1


@pytest.mark.parametrize(
    "start", ["2026-03-27T12:00:00+01:00", "2026-10-23T12:00:00+02:00"]
)
def test_week_uses_seven_local_dates_across_dst(database, start) -> None:
    from datetime import time
    from zoneinfo import ZoneInfo

    _, uow = database
    now = datetime.fromisoformat(start).astimezone(ZoneInfo("Europe/Vienna"))
    midnight = datetime.combine(now.date(), time.min, now.tzinfo)
    with uow.transaction() as repos:
        cid = repos.courses.upsert(CourseData("194025", "2026S", "Course"), now)
        for key, at in [
            ("before", midnight - timedelta(seconds=1)),
            ("today", midnight),
            ("last", midnight + timedelta(days=7, seconds=-1)),
            ("outside", midnight + timedelta(days=7)),
        ]:
            repos.events.upsert(cid, EventData(key, at, "tiss", key), now)
    assert [
        item.event.title for item in EventService(uow).overview(week=True, now=now)
    ] == ["today", "last"]


def test_due_update_between_dst_fold_instants(database) -> None:
    from zoneinfo import ZoneInfo

    engine, uow = database
    at = datetime(2026, 10, 25, 2, 30, tzinfo=ZoneInfo("Europe/Vienna"))
    with uow.transaction() as repos:
        cid = repos.courses.upsert(CourseData("194025", "2026S", "Course"), NOW)
        eid = repos.events.upsert(
            cid,
            EventData(
                "Deadline",
                None,
                "tuwel",
                "assign:1",
                due_at=at,
                event_type="assignment",
            ),
            NOW,
        )
    with uow.transaction() as repos:
        assert (
            repos.events.upsert(
                cid,
                EventData(
                    "Deadline",
                    None,
                    "tuwel",
                    "assign:1",
                    due_at=at.replace(fold=1),
                    event_type="assignment",
                ),
                NOW + timedelta(hours=1),
            )
            == eid
        )
    with build_session_factory(engine)() as session:
        event = session.get(Event, eid)
        assert event.due_at.fold == 1
        assert event.due_at.utcoffset() == timedelta(hours=1)
        assert event.updated_at == NOW + timedelta(hours=1)


def test_m3_upgrade_preserves_existing_m2_exam(database) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    engine, _ = database
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    command.downgrade(config, "0002_courses_events")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO courses (id, course_code, semester, name, "
                "created_at, updated_at) "
                "VALUES (1, '194025', '2026S', 'ML', '2026-09-01', '2026-09-01')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO events (id, course_id, title, event_type, starts_at, "
                "source, source_id, "
                "first_seen_at, last_seen_at, created_at, updated_at) "
                "VALUES (1, 1, 'Exam', 'exam', '2026-10-12 08:00:00', "
                "'tiss', '528535', "
                "'2026-09-01', '2026-09-01', '2026-09-01', '2026-09-01')"
            )
        )
    command.upgrade(config, "head")
    command.check(config)
    with build_session_factory(engine)() as session:
        event = session.get(Event, 1)
        assert event.source_id == "528535"
        assert event.starts_at.hour == 10
        assert event.due_at is None
        assert event.submission_status is None
