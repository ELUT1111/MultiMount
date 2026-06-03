"""Datetime serialization helpers."""
from datetime import datetime, timezone


def iso_utc(value: datetime | None) -> str | None:
    """Serialize datetimes as explicit UTC ISO strings for browser parsing."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")
