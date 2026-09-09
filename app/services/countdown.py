from datetime import datetime
from zoneinfo import ZoneInfo

VIENNA = ZoneInfo("Europe/Vienna")


def days_until(starts_at: datetime, now: datetime) -> int:
    """Compare local calendar dates, including on 23/25-hour DST days."""
    if starts_at.utcoffset() is None or now.utcoffset() is None:
        raise ValueError("Countdown requires timezone-aware datetimes")
    return (starts_at.astimezone(VIENNA).date() - now.astimezone(VIENNA).date()).days
