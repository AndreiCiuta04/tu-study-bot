from datetime import datetime, time

from app.entities.events import ExamOverview
from app.repositories.unit_of_work import UnitOfWork
from app.services.countdown import VIENNA, days_until


class ExamService:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    def upcoming(self, now: datetime | None = None) -> tuple[ExamOverview, ...]:
        now = now if now is not None else datetime.now(VIENNA)
        if now.utcoffset() is None:
            raise ValueError("Exam overview requires a timezone-aware clock")
        # Include all exams on today's Vienna date, even if their time has passed.
        start = datetime.combine(now.astimezone(VIENNA).date(), time.min, VIENNA)
        with self._unit_of_work.transaction() as repositories:
            exams = repositories.events.upcoming_exams(start)
        return tuple(
            ExamOverview(exam, days_until(exam.starts_at, now)) for exam in exams
        )
