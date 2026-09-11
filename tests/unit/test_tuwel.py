import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.config.settings import TuwelSettings
from app.integrations.tuwel.auth import TokenAuth
from app.integrations.tuwel.client import ENDPOINT, TuwelClient
from app.integrations.tuwel.dtos import (
    Assignment,
    CalendarEvent,
    Course,
    SubmissionResponse,
)
from app.integrations.tuwel.errors import (
    TuwelAccessError,
    TuwelAuthenticationError,
    TuwelNetworkError,
    TuwelResponseError,
)
from app.integrations.tuwel.mapper import (
    CourseMapping,
    map_assignment,
    map_calendar,
    map_course,
    timestamp,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "tuwel"


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def test_course_resolution_is_explicit() -> None:
    course = Course.model_validate(fixture("courses")[0])
    mapping = CourseMapping(course_code="194.025", semester="2026S")
    result = map_course(course, mapping)
    assert (result.course_code, result.semester) == ("194025", "2026S")
    with pytest.raises(ValueError, match="conflicts"):
        map_course(course, CourseMapping(course_code="999999", semester="2026S"))
    with pytest.raises(ValidationError):
        CourseMapping(course_code="194025", semester="autumn")
    arbitrary = course.model_copy(update={"idnumber": "arbitrary"})
    assert map_course(arbitrary, mapping).semester == "2026S"


def test_assignment_mapping_and_submission() -> None:
    assignment = Assignment.model_validate(
        fixture("assignments")["courses"][0]["assignments"][0]
    )
    submission = SubmissionResponse.model_validate(fixture("submission"))
    event = map_assignment(assignment, submission, 42)
    assert event.source == "tuwel"
    assert event.source_id == "assign:501"
    assert event.source_url == "https://tuwel.tuwien.ac.at/mod/assign/view.php?id=601"
    assert event.starts_at is None
    assert event.due_at == timestamp(assignment.duedate)
    assert event.submission_status == "submitted"
    assert map_assignment(assignment, None, 42).submission_status is None
    assert (
        map_assignment(
            assignment.model_copy(update={"teamsubmission": 1}), submission, 42
        ).submission_status
        is None
    )
    with pytest.raises(ValueError, match="different user"):
        map_assignment(assignment, submission, 99)


@pytest.mark.parametrize(
    "status", ["new", "draft", "reopened", "submitted", "unrecognized"]
)
def test_submission_state_is_not_inferred(status) -> None:
    assignment = Assignment.model_validate(
        fixture("assignments")["courses"][0]["assignments"][0]
    )
    submission = SubmissionResponse.model_validate(
        {
            "lastattempt": {
                "submission": {"status": status},
                "extensionduedate": assignment.duedate + 86400,
            },
            "feedback": {"grade": 100},
        }
    )
    result = map_assignment(assignment, submission, 42)
    assert result.submission_status == (None if status == "unrecognized" else status)
    assert result.due_at == timestamp(assignment.duedate + 86400)
    assert (
        map_assignment(
            assignment,
            SubmissionResponse.model_validate({"feedback": {"grade": 100}}),
            42,
        ).submission_status
        is None
    )


def test_no_due_date_is_unknown() -> None:
    assignment = Assignment.model_validate(
        fixture("assignments")["courses"][0]["assignments"][0]
    )
    assert (
        map_assignment(assignment.model_copy(update={"duedate": 0}), None, 42).due_at
        is None
    )


def test_calendar_mapping_uses_explicit_activity_ids_and_types() -> None:
    raw = fixture("calendar")["events"]
    event = map_calendar(CalendarEvent.model_validate(raw[0]))
    assert event.source_id == "assign:501"
    assert event.event_type == "assignment"
    quiz = map_calendar(CalendarEvent.model_validate(raw[1]))
    assert quiz.event_type == "quiz"
    assert quiz.due_at is not None
    assert quiz.source_id == "calendar:702"
    other = map_calendar(
        CalendarEvent.model_validate(
            {
                **raw[1],
                "modulename": "",
                "eventtype": "course",
                "name": "UE-Test",
            }
        )
    )
    assert other.event_type == "other"
    assert other.due_at is None
    assert other.starts_at is not None


@pytest.mark.parametrize(
    ("value", "hours"),
    [("2026-01-01T10:00:00+00:00", 1), ("2026-07-01T10:00:00+00:00", 2)],
)
def test_unix_timestamps_convert_to_vienna(value, hours) -> None:
    original = datetime.fromisoformat(value)
    result = timestamp(int(original.timestamp()))
    assert result == original
    assert result.utcoffset() == timedelta(hours=hours)
    assert str(result.tzinfo) == "Europe/Vienna"
    assert timestamp(0) is None


@pytest.mark.parametrize(
    ("payload", "status", "error"),
    [
        (
            {"errorcode": "invalidtoken", "message": "SECRET"},
            200,
            TuwelAuthenticationError,
        ),
        ({"errorcode": "accessexception", "message": "SECRET"}, 200, TuwelAccessError),
        ({}, 401, TuwelAuthenticationError),
        ({}, 403, TuwelAccessError),
        ({}, 503, TuwelNetworkError),
        ({"warnings": [{"message": "SECRET"}], "courses": []}, 200, TuwelResponseError),
        ({"unexpected": "SECRET"}, 200, TuwelResponseError),
        (None, 200, TuwelResponseError),
    ],
)
def test_typed_errors_never_expose_response_or_token(payload, status, error) -> None:
    def respond(request):
        assert request.method == "POST"
        assert str(request.url) == ENDPOINT
        params = parse_qs(request.content.decode())
        assert params["wstoken"] == ["TEST_TOKEN"]
        return httpx.Response(status, json=payload)

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            return await TuwelClient(
                http, TokenAuth(SecretStr("TEST_TOKEN"))
            ).site_info()

    with pytest.raises(error) as caught:
        asyncio.run(call())
    assert "SECRET" not in str(caught.value)
    assert "TEST_TOKEN" not in str(caught.value)


@pytest.mark.parametrize("failure", ["timeout", "html"])
def test_network_and_non_json_failure(failure) -> None:
    def respond(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("private token details")
        return httpx.Response(200, text="<html>Login</html>")

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            return await TuwelClient(http, TokenAuth(SecretStr("TEST_TOKEN"))).courses(
                42
            )

    with pytest.raises(
        TuwelNetworkError if failure == "timeout" else TuwelResponseError
    ):
        asyncio.run(call())


def test_token_settings_and_empty_token(monkeypatch) -> None:
    monkeypatch.setenv("TUW_TUWEL_TOKEN", "TEST_TOKEN")
    monkeypatch.setenv(
        "TUW_TUWEL_COURSES", '{"101":{"course_code":"194.025","semester":"2026S"}}'
    )
    settings = TuwelSettings(_env_file=None)
    assert settings.tuwel_courses[101].course_code == "194025"
    assert "TEST_TOKEN" not in repr(settings)
    with pytest.raises(TuwelAuthenticationError):
        TokenAuth(SecretStr(" ")).token()


def test_client_empty_course_ids_do_not_request_all_courses() -> None:
    async def call():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: pytest.fail("unexpected request")
            )
        ) as http:
            client = TuwelClient(http, TokenAuth(SecretStr("TEST_TOKEN")))
            assert (await client.assignments(())).courses == ()
            assert (await client.calendar((), 0, 0)).events == ()

    asyncio.run(call())
