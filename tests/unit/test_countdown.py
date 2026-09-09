from datetime import datetime

import pytest

from app.services.countdown import days_until


@pytest.mark.parametrize(
    ("now", "exam", "expected"),
    [
        ("2027-01-09T23:59:00+01:00", "2027-01-28T08:00:00+01:00", 19),
        ("2027-01-09T23:59:00+01:00", "2027-01-10T00:01:00+01:00", 1),
        ("2027-01-09T23:59:00+01:00", "2027-01-09T08:00:00+01:00", 0),
        ("2026-03-28T23:59:00+01:00", "2026-03-29T23:00:00+02:00", 1),
        ("2026-10-24T00:01:00+02:00", "2026-10-25T23:59:00+01:00", 1),
        ("2027-01-09T23:30:00+00:00", "2027-01-10T10:00:00+01:00", 0),
        ("2027-01-10T00:00:00+01:00", "2027-01-09T23:59:00+01:00", -1),
    ],
)
def test_calendar_countdown(now, exam, expected) -> None:
    assert (
        days_until(datetime.fromisoformat(exam), datetime.fromisoformat(now))
        == expected
    )


def test_naive_clock_rejected() -> None:
    with pytest.raises(ValueError):
        days_until(datetime(2027, 1, 10), datetime(2027, 1, 9))
