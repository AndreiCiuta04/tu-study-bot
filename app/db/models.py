"""Persistence models; application access is restricted to repositories."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import AwareDateTime


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("course_code", "semester"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_code: Mapped[str] = mapped_column(String(16))
    semester: Mapped[str] = mapped_column(String(5))
    name: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(AwareDateTime())
    updated_at: Mapped[datetime] = mapped_column(AwareDateTime())


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source", "source_id"),
        Index("ix_events_type_starts_at", "event_type", "starts_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(500))
    starts_at: Mapped[datetime | None] = mapped_column(AwareDateTime())
    due_at: Mapped[datetime | None] = mapped_column(AwareDateTime(), index=True)
    submission_status: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(2000))
    first_seen_at: Mapped[datetime] = mapped_column(AwareDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(AwareDateTime())
    created_at: Mapped[datetime] = mapped_column(AwareDateTime())
    updated_at: Mapped[datetime] = mapped_column(AwareDateTime())
