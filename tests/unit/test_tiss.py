import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.integrations.tiss.client import (
    TissClient,
    TissPayloadError,
    normalize_course_number,
    parse_course,
    parse_exams,
)
from app.integrations.tiss.mapper import map_course, map_exam, vienna_time

FIXTURES = Path(__file__).parents[1] / "fixtures" / "tiss"


def test_real_payload_mapping() -> None:
    course = parse_course((FIXTURES / "course.xml").read_bytes())
    exams = parse_exams((FIXTURES / "exam_dates.xml").read_bytes())
    assert map_course(course).course_code == "194025"
    assert course.title == "Introduction to Machine Learning"
    assert len(exams) == 1
    assert exams[0].application_end == datetime.fromisoformat(
        "2026-09-06T23:59:00+02:00"
    )
    assert exams[0].deregistration_end == datetime.fromisoformat(
        "2026-09-07T23:59:00+02:00"
    )
    exam = map_exam(exams[0], course)
    assert exam.source_id == "528535"
    assert exam.source == "tiss"
    assert exam.event_type == "exam"
    assert exam.title == "Exam 2nd Attempt  (2026-09-09)"
    assert str(exam.starts_at.tzinfo) == "Europe/Vienna"
    assert exam.starts_at.hour == 10
    assert exam.source_url.endswith("courseNr=194025&semester=2026S")


@pytest.mark.parametrize("code", ["194025", "194.025", " 194.025 "])
def test_course_normalization(code) -> None:
    assert normalize_course_number(code) == "194025"


@pytest.mark.parametrize("code", ["194..025", "../abc", "19402", "1940257"])
def test_invalid_course_number(code) -> None:
    with pytest.raises(ValueError):
        normalize_course_number(code)


@pytest.mark.parametrize(
    ("value", "hour", "offset"),
    [
        ("2027-01-28T09:00:00", 9, 1),
        ("2027-07-28T09:00:00", 9, 2),
        ("2027-07-28T07:00:00+00:00", 9, 2),
    ],
)
def test_vienna_mapping(value, hour, offset) -> None:
    result = vienna_time(datetime.fromisoformat(value))
    assert result.hour == hour
    assert result.utcoffset() == timedelta(hours=offset)


@pytest.mark.parametrize("value", ["2026-03-29T02:30:00", "2026-10-25T02:30:00"])
def test_ambiguous_or_nonexistent_floating_time_is_rejected(value) -> None:
    with pytest.raises(ValueError):
        vienna_time(datetime.fromisoformat(value))


def test_missing_real_id_is_rejected_not_fabricated() -> None:
    payload = (FIXTURES / "exam_dates.xml").read_bytes().replace(b' id="528535"', b"")
    with pytest.raises(ValidationError):
        parse_exams(payload)


@pytest.mark.parametrize(
    "payload",
    [
        b"<html>Login</html>",
        b'<tuvienna xmlns="https://tiss.tuwien.ac.at/api/schemas/exams/v10"><error/></tuvienna>',
    ],
)
def test_unexpected_payload_rejected(payload) -> None:
    with pytest.raises(TissPayloadError):
        parse_exams(payload)


def test_empty_payload() -> None:
    assert (
        parse_exams(
            b'<tuvienna xmlns="https://tiss.tuwien.ac.at/api/schemas/exams/v10"/>'
        )
        == ()
    )


@pytest.mark.parametrize("status", [200, 404, 500])
def test_public_client_request_and_status(status) -> None:
    def respond(request):
        assert request.url.path == "/api/course/194025/examDates"
        assert request.url.params["fromDate"] == "2026-09-09"
        return httpx.Response(
            status, content=(FIXTURES / "exam_dates.xml").read_bytes()
        )

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            return await TissClient(http).exams("194.025", date(2026, 9, 9))

    if status == 500:
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(exercise())
    else:
        assert len(asyncio.run(exercise())) == (0 if status == 404 else 1)


def test_course_endpoint_and_network_error() -> None:
    def respond(request):
        assert request.url.path == "/api/course/194025-2026S"
        raise httpx.ConnectError("offline", request=request)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            return await TissClient(http).course("194.025", "2026S")

    with pytest.raises(httpx.ConnectError):
        asyncio.run(exercise())
