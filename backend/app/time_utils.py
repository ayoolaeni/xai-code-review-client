"""Time helpers. SQLite returns naive datetimes; all stored values are UTC."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")


def as_utc(value: dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.UTC)
    return value.astimezone(dt.UTC)


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def pacific_day(now: dt.datetime | None = None) -> dt.date:
    """The Gemini daily quota resets at midnight US Pacific time."""
    return (now or now_utc()).astimezone(PACIFIC).date()


def next_pacific_midnight_utc(now: dt.datetime | None = None) -> dt.datetime:
    local = (now or now_utc()).astimezone(PACIFIC)
    tomorrow = (local + dt.timedelta(days=1)).date()
    midnight = dt.datetime.combine(tomorrow, dt.time(0, 0), tzinfo=PACIFIC)
    return midnight.astimezone(dt.UTC)
