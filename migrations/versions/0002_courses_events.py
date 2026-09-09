"""Course offerings and provenance-preserving events."""

import sqlalchemy as sa
from alembic import op

revision = "0002_courses_events"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_code", sa.String(16), nullable=False),
        sa.Column("semester", sa.String(5), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("course_code", "semester", name="uq_courses_course_code"),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(2000)),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source", "source_id", name="uq_events_source"),
    )
    op.create_index("ix_events_course_id", "events", ["course_id"])
    op.create_index("ix_events_type_starts_at", "events", ["event_type", "starts_at"])


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("courses")
