from datetime import datetime, time, timedelta

from app.entities.events import EventOverview
from app.repositories.unit_of_work import UnitOfWork
from app.services.countdown import VIENNA, days_until


class EventService:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    def overview(
        self,
        *,
        week: bool = False,
        now: datetime | None = None,
    ) -> tuple[EventOverview, ...]:
        now = now if now is not None else datetime.now(VIENNA)
        if now.utcoffset() is None:
            raise ValueError("Overview requires a timezone-aware clock")
        start = datetime.combine(now.astimezone(VIENNA).date(), time.min, VIENNA)
        end = start + timedelta(days=7) if week else None
        with self._unit_of_work.transaction() as repositories:
            events = repositories.events.scheduled(start, end, deadlines_only=not week)
        return tuple(
            EventOverview(event, days_until(event.occurs_at, now)) for event in events
        )
