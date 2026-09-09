"""Repository transaction boundary; services never receive SQLAlchemy sessions."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from app.repositories.course_repository import CourseRepository
from app.repositories.event_repository import EventRepository


class Repositories:
    def __init__(self, session: Session) -> None:
        self.courses = CourseRepository(session)
        self.events = EventRepository(session)


class UnitOfWork:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    @contextmanager
    def transaction(self) -> Iterator[Repositories]:
        with self._factory.begin() as session:
            yield Repositories(session)
