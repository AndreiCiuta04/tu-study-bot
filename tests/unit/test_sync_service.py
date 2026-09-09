import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.tiss.dtos import TissCourse, TissExam
from app.services.sync_service import SyncService


def test_service_orchestrates_normalization_and_repositories() -> None:
    client = MagicMock()
    client.course = AsyncMock(
        return_value=TissCourse(
            course_number="194025", semester_code="2026S", title="Machine Learning"
        )
    )
    client.exams = AsyncMock(
        return_value=(
            TissExam(
                id="528535", title="Exam", examination_begin=datetime(2027, 1, 28, 10)
            ),
        )
    )
    uow = MagicMock()
    repositories = uow.transaction.return_value.__enter__.return_value
    repositories.courses.upsert.return_value = 7
    assert asyncio.run(SyncService(client, uow).sync_exams("194.025", "2026S")) == 1
    client.course.assert_awaited_once_with("194025", "2026S")
    client.exams.assert_awaited_once_with("194025", None)
    course, seen_at = repositories.courses.upsert.call_args.args
    assert course.course_code == "194025"
    assert course.semester == "2026S"
    course_id, event, event_seen_at = repositories.events.upsert.call_args.args
    assert course_id == 7
    assert event.source_id == "528535"
    assert event.starts_at.utcoffset().total_seconds() == 3600
    assert event_seen_at == seen_at
    uow.transaction.return_value.__exit__.assert_called_once_with(None, None, None)


def test_mismatched_offering_never_opens_transaction() -> None:
    client = MagicMock()
    client.course = AsyncMock(
        return_value=TissCourse(
            course_number="194025", semester_code="2025W", title="Machine Learning"
        )
    )
    client.exams = AsyncMock()
    uow = MagicMock()
    with pytest.raises(ValueError, match="different course"):
        asyncio.run(SyncService(client, uow).sync_exams("194025", "2026S"))
    client.exams.assert_not_awaited()
    uow.transaction.assert_not_called()
