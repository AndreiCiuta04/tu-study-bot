"""Immutable values crossing the service/repository boundary."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CourseData:
    course_code: str
    semester: str
    name: str


@dataclass(frozen=True)
class EventData:
    title: str
    starts_at: datetime | None
    source: str
    source_id: str
    source_url: str | None = None
    event_type: str = "exam"
    due_at: datetime | None = None
    submission_status: str | None = None


@dataclass(frozen=True)
class Exam:
    id: int
    course_name: str
    title: str
    starts_at: datetime
    source_url: str | None


@dataclass(frozen=True)
class ExamOverview:
    exam: Exam
    days_remaining: int


@dataclass(frozen=True)
class ScheduledEvent:
    id: int
    course_name: str
    title: str
    occurs_at: datetime
    event_type: str
    source: str
    source_url: str | None
    submission_status: str | None


@dataclass(frozen=True)
class EventOverview:
    event: ScheduledEvent
    days_remaining: int
