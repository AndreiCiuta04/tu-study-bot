from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.entities.events import CourseData, EventData
from app.integrations.tiss.dtos import TissCourse, TissExam

VIENNA = ZoneInfo("Europe/Vienna")


def vienna_time(value: datetime) -> datetime:
    if value.utcoffset() is not None:
        return value.astimezone(VIENNA)
    local = value.replace(tzinfo=VIENNA)
    if (
        local.astimezone(UTC).astimezone(VIENNA).replace(tzinfo=None) != value
        or local.utcoffset() != local.replace(fold=1).utcoffset()
    ):
        raise ValueError("Ambiguous or nonexistent Vienna start time")
    return local


def map_course(course: TissCourse) -> CourseData:
    return CourseData(course.course_number, course.semester_code, course.title)


def map_exam(exam: TissExam, course: TissCourse) -> EventData:
    return EventData(
        title=exam.title,
        starts_at=vienna_time(exam.examination_begin),
        source="tiss",
        source_id=exam.id,
        source_url=(
            "https://tiss.tuwien.ac.at/course/courseDetails.xhtml"
            f"?courseNr={course.course_number}&semester={course.semester_code}"
        ),
    )
