"""Support deadlines and explicitly reported submission state."""

import sqlalchemy as sa
from alembic import op

revision = "0003_tuwel_deadlines"
down_revision = "0002_courses_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("events") as batch:
        batch.alter_column("starts_at", existing_type=sa.DateTime(), nullable=True)
        batch.add_column(sa.Column("due_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("submission_status", sa.String(32), nullable=True))
        batch.create_index("ix_events_due_at", ["due_at"])


def downgrade() -> None:
    # Preflight before writing: M2 cannot represent an undated assignment.
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT COUNT(*) FROM events WHERE starts_at IS NULL AND due_at IS NULL"
        )
    ):
        raise RuntimeError("Cannot downgrade while unscheduled events exist")
    op.execute(
        "UPDATE events SET starts_at = due_at "
        "WHERE starts_at IS NULL AND due_at IS NOT NULL"
    )
    with op.batch_alter_table("events") as batch:
        batch.drop_index("ix_events_due_at")
        batch.drop_column("submission_status")
        batch.drop_column("due_at")
        batch.alter_column("starts_at", existing_type=sa.DateTime(), nullable=False)
