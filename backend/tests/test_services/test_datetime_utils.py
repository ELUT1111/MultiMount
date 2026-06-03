from datetime import datetime, timezone, timedelta

from app.utils.datetime_utils import iso_utc


def test_iso_utc_marks_naive_datetime_as_utc():
    value = datetime(2026, 6, 3, 14, 56, 34)

    assert iso_utc(value) == "2026-06-03T14:56:34Z"


def test_iso_utc_converts_aware_datetime_to_utc():
    value = datetime(2026, 6, 3, 22, 56, 34, tzinfo=timezone(timedelta(hours=8)))

    assert iso_utc(value) == "2026-06-03T14:56:34Z"


def test_iso_utc_allows_none():
    assert iso_utc(None) is None
