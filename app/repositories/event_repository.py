from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Course, Event
from app.entities.events import EventData, Exam, ScheduledEvent


def _same_value(current: object, incoming: object) -> bool:
    if isinstance(current, datetime) and isinstance(incoming, datetime):
        if current.utcoffset() is None or incoming.utcoffset() is None:
            return False
        # Python compares matching ZoneInfo objects by wall time, ignoring fold.
        return current.astimezone(UTC) == incoming.astimezone(UTC)
    return current == incoming


class EventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, course_id: int, data: EventData, seen_at: datetime) -> int:
        event = self._session.scalar(
            select(Event).where(
                Event.source == data.source, Event.source_id == data.source_id
            )
        )
        values = {
            "course_id": course_id,
            "event_type": data.event_type,
            "title": data.title,
            "starts_at": data.starts_at,
            "source_url": data.source_url,
            "due_at": data.due_at,
            "submission_status": data.submission_status,
        }
        if event is None:
            event = Event(
                **values,
                source=data.source,
                source_id=data.source_id,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
                created_at=seen_at,
                updated_at=seen_at,
            )
            self._session.add(event)
        else:
            if any(
                not _same_value(getattr(event, key), value)
                for key, value in values.items()
            ):
                for key, value in values.items():
                    setattr(event, key, value)
                event.updated_at = seen_at
            event.last_seen_at = seen_at
        self._session.flush()
        return event.id

    def upcoming_exams(self, since: datetime) -> tuple[Exam, ...]:
        rows = self._session.execute(
            select(Event, Course.name)
            .join(Course, Event.course_id == Course.id)
            .where(Event.event_type == "exam", Event.starts_at >= since)
            .order_by(Event.starts_at, Course.name, Event.id)
        )
        return tuple(
            Exam(event.id, name, event.title, event.starts_at, event.source_url)
            for event, name in rows
            if event.starts_at is not None
        )

    def scheduled(
        self,
        since: datetime,
        until: datetime | None = None,
        *,
        deadlines_only: bool = False,
    ) -> tuple[ScheduledEvent, ...]:
        occurrence = (
            Event.due_at
            if deadlines_only
            else func.coalesce(Event.due_at, Event.starts_at)
        )
        query = (
            select(Event, Course.name, occurrence)
            .join(Course)
            .where(occurrence >= since)
        )
        if until is not None:
            query = query.where(occurrence < until)
        if deadlines_only:
            query = query.where(
                Event.event_type.in_(("assignment", "submission_deadline", "quiz"))
            )
        rows = self._session.execute(query.order_by(occurrence, Course.name, Event.id))
        return tuple(
            ScheduledEvent(
                event.id,
                name,
                event.title,
                at,
                event.event_type,
                event.source,
                event.source_url,
                event.submission_status,
            )
            for event, name, at in rows
        )
