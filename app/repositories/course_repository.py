from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Course
from app.entities.events import CourseData


class CourseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, data: CourseData, seen_at: datetime) -> int:
        course = self._session.scalar(
            select(Course).where(
                Course.course_code == data.course_code, Course.semester == data.semester
            )
        )
        if course is None:
            course = Course(
                course_code=data.course_code,
                semester=data.semester,
                name=data.name,
                created_at=seen_at,
                updated_at=seen_at,
            )
            self._session.add(course)
        elif course.name != data.name:
            course.name = data.name
            course.updated_at = seen_at
        self._session.flush()
        return course.id
