"""Round-trip aware instants consistently on SQLite and PostgreSQL."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class AwareDateTime(TypeDecorator[datetime]):
    impl = DateTime
    cache_ok = True

    def compare_values(self, x: object, y: object) -> bool:
        if isinstance(x, datetime) and isinstance(y, datetime):
            if x.utcoffset() is None or y.utcoffset() is None:
                return False
            return x.astimezone(UTC) == y.astimezone(UTC)
        return x == y

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("Persistence requires timezone-aware datetimes")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC).astimezone(ZoneInfo("Europe/Vienna"))
