from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Course, Event
from app.entities.events import EventData, Exam


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
            if any(getattr(event, key) != value for key, value in values.items()):
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
        )
