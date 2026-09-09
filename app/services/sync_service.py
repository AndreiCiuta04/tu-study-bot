from datetime import date, datetime

from app.integrations.tiss.client import TissClient, normalize_course_number
from app.integrations.tiss.mapper import map_course, map_exam
from app.repositories.unit_of_work import UnitOfWork
from app.services.countdown import VIENNA


class SyncService:
    def __init__(self, client: TissClient, unit_of_work: UnitOfWork) -> None:
        self._client = client
        self._unit_of_work = unit_of_work

    async def sync_exams(
        self, course_code: str, semester: str, from_date: date | None = None
    ) -> int:
        course_code = normalize_course_number(course_code)
        course = await self._client.course(course_code, semester)
        if (course.course_number, course.semester_code) != (course_code, semester):
            raise ValueError("TISS returned a different course offering")
        exams = await self._client.exams(course_code, from_date)
        normalized = [map_exam(exam, course) for exam in exams]
        # Fetch and validate everything before opening an atomic write transaction.
        seen_at = datetime.now(VIENNA)
        with self._unit_of_work.transaction() as repositories:
            course_id = repositories.courses.upsert(map_course(course), seen_at)
            for exam in normalized:
                repositories.events.upsert(course_id, exam, seen_at)
        return len(normalized)
