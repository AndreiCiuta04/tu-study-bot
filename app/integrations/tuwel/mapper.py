"""Explicit identity resolution and source-to-domain normalization."""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.entities.events import CourseData, EventData
from app.integrations.tuwel.dtos import (
    Assignment,
    CalendarEvent,
    Course,
    SubmissionResponse,
)

BASE_URL = "https://tuwel.tuwien.ac.at"


class CourseMapping(BaseModel):
    model_config = ConfigDict(frozen=True)
    course_code: str = Field(pattern=r"^[0-9A-Z]{6}$")
    semester: str = Field(pattern=r"^\d{4}[SW]$")

    @field_validator("course_code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        if isinstance(value, str) and re.fullmatch(
            r"[0-9A-Z]{3}\.?[0-9A-Z]{3}", value.strip().upper()
        ):
            return value.strip().upper().replace(".", "")
        return value


def map_course(course: Course, mapping: CourseMapping) -> CourseData:
    # Moodle defines idnumber as arbitrary text: never infer a semester from it.
    # If it is exactly a TU course number, verify the explicit mapping agrees.
    if re.fullmatch(r"[0-9A-Z]{3}\.?[0-9A-Z]{3}", course.idnumber):
        if course.idnumber.replace(".", "") != mapping.course_code:
            raise ValueError("TUWEL course number conflicts with configured mapping")
    return CourseData(mapping.course_code, mapping.semester, course.fullname)


def timestamp(value: int) -> datetime | None:
    if value == 0:
        return None
    return datetime.fromtimestamp(value, UTC).astimezone(ZoneInfo("Europe/Vienna"))


def map_assignment(
    assignment: Assignment, submission: SubmissionResponse | None, userid: int
) -> EventData:
    due = timestamp(assignment.duedate)
    state = None
    attempt = submission.lastattempt if submission else None
    if attempt:
        if attempt.extensionduedate:
            due = timestamp(attempt.extensionduedate)
        # Group submissions do not prove that this individual has submitted.
        if not assignment.teamsubmission and attempt.submission:
            item = attempt.submission
            if item.userid not in (None, userid):
                raise ValueError("Submission belongs to a different user")
            if item.status in ("new", "draft", "submitted", "reopened"):
                state = item.status
    return EventData(
        title=assignment.name,
        starts_at=timestamp(assignment.allowsubmissionsfromdate),
        due_at=due,
        source="tuwel",
        source_id=f"assign:{assignment.id}",
        source_url=f"{BASE_URL}/mod/assign/view.php?id={assignment.cmid}",
        event_type="assignment",
        submission_status=state,
    )


def map_calendar(event: CalendarEvent) -> EventData:
    at = timestamp(event.timestart)
    is_due = event.eventtype in ("due", "close")
    kind = "other"
    if event.modulename == "quiz":
        kind = "quiz"
    elif is_due:
        kind = "submission_deadline"
    source_id = f"calendar:{event.id}"
    if event.modulename == "assign" and event.instance > 0 and event.eventtype == "due":
        source_id = f"assign:{event.instance}"
        kind = "assignment"
    return EventData(
        title=event.name,
        starts_at=None if is_due else at,
        due_at=at if is_due else None,
        source="tuwel",
        source_id=source_id,
        event_type=kind,
        source_url=f"{BASE_URL}/calendar/view.php?view=event&id={event.id}",
    )
