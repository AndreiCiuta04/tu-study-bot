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
    starts_at: datetime
    source: str
    source_id: str
    source_url: str | None = None
    event_type: str = "exam"


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
