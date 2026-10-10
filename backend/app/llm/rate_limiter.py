"""Gemini free-tier pacing: per-minute request pacer and daily quota tracker (Section 8.9.6)."""

from __future__ import annotations

import datetime as dt
import logging
import threading
import time
from collections import deque
from collections.abc import Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.db import SessionLocal
from app.llm.client import LLMError
from app.models import LLMUsage
from app.time_utils import next_pacific_midnight_utc, now_utc, pacific_day

log = logging.getLogger(__name__)

WINDOW_SECONDS = 60.0
MAX_WAIT_SECONDS = 90.0


class RequestPacer:
    """Process-wide sliding window: at most `per_minute` requests in any rolling 60 s."""

    def __init__(
        self,
        per_minute: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        max_wait: float = MAX_WAIT_SECONDS,
    ):
        self.per_minute = max(1, per_minute)
        self._clock = clock
        self._sleep = sleep
        self._max_wait = max_wait
        self._times: deque[float] = deque()
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        while self._times and now - self._times[0] >= WINDOW_SECONDS:
            self._times.popleft()

    def try_acquire(self) -> bool:
        with self._lock:
            now = self._clock()
            self._prune(now)
            if len(self._times) < self.per_minute:
                self._times.append(now)
                return True
            return False

    def acquire(self) -> float:
        """Block until a slot is free. Returns the seconds waited; raises rate_limit after max_wait."""
        start = self._clock()
        while True:
            with self._lock:
                now = self._clock()
                self._prune(now)
                if len(self._times) < self.per_minute:
                    self._times.append(now)
                    return now - start
                wait = WINDOW_SECONDS - (now - self._times[0])
            if (now - start) + wait > self._max_wait:
                raise LLMError("rate_limit", "Waited too long for a free AI request slot.")
            self._sleep(max(0.05, min(wait, 1.0)))

    def in_window(self) -> int:
        with self._lock:
            self._prune(self._clock())
            return len(self._times)


class DailyQuota:
    """Counts Gemini requests per Pacific-time day in the `llm_usage` table."""

    def __init__(
        self,
        limit: Callable[[], int],
        now: Callable[[], dt.datetime] = now_utc,
        session_factory=SessionLocal,
    ):
        self._limit = limit
        self._now = now
        self._session_factory = session_factory

    @property
    def limit(self) -> int:
        return self._limit()

    def today(self) -> dt.date:
        return pacific_day(self._now())

    def usage_today(self) -> dict[str, int]:
        with self._session_factory() as db:
            row = db.get(LLMUsage, self.today())
            if row is None:
                return {"requests": 0, "input_tokens": 0, "output_tokens": 0}
            return {
                "requests": row.requests,
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
            }

    def used_today(self) -> int:
        return self.usage_today()["requests"]

    def remaining_fraction(self) -> float:
        limit = self.limit
        if limit <= 0:
            return 0.0
        return max(0.0, (limit - self.used_today()) / limit)

    def reset_time_utc(self) -> dt.datetime:
        return next_pacific_midnight_utc(self._now())

    def check(self) -> None:
        if self.used_today() >= self.limit:
            raise LLMError("quota_exhausted", "The free AI quota for today has been used up.")

    def record(self, input_tokens: int | None = None, output_tokens: int | None = None) -> None:
        """Atomic `requests = requests + 1` (inserting today's row if missing)."""
        day = self.today()
        values = {
            "requests": LLMUsage.requests + 1,
            "input_tokens": LLMUsage.input_tokens + (input_tokens or 0),
            "output_tokens": LLMUsage.output_tokens + (output_tokens or 0),
        }
        for _ in range(3):
            with self._session_factory() as db:
                result = db.execute(update(LLMUsage).where(LLMUsage.day == day).values(**values))
                if result.rowcount:
                    db.commit()
                    return
                try:
                    db.add(
                        LLMUsage(
                            day=day,
                            requests=1,
                            input_tokens=input_tokens or 0,
                            output_tokens=output_tokens or 0,
                        )
                    )
                    db.commit()
                    return
                except IntegrityError:
                    db.rollback()  # another thread inserted the row first — retry the update
        log.warning("could not record LLM usage")

    def exhaust_today(self) -> None:
        """The API reported a daily-quota 429: treat the rest of the day as used up."""
        day = self.today()
        with self._session_factory() as db:
            row = db.get(LLMUsage, day)
            if row is None:
                db.add(LLMUsage(day=day, requests=self.limit, input_tokens=0, output_tokens=0))
            else:
                row.requests = max(row.requests, self.limit)
            db.commit()

    def history(self, days: int = 30) -> list[dict]:
        since = self.today() - dt.timedelta(days=days - 1)
        with self._session_factory() as db:
            rows = db.scalars(select(LLMUsage).where(LLMUsage.day >= since).order_by(LLMUsage.day)).all()
            return [
                {
                    "date": r.day.isoformat(),
                    "requests": r.requests,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                }
                for r in rows
            ]


_lock = threading.Lock()
_pacer: RequestPacer | None = None
_quota: DailyQuota | None = None


def get_pacer() -> RequestPacer:
    global _pacer
    with _lock:
        rpm = get_settings().GEMINI_REQUESTS_PER_MINUTE
        if _pacer is None:
            _pacer = RequestPacer(rpm)
        _pacer.per_minute = max(1, rpm)
        return _pacer


def get_quota() -> DailyQuota:
    global _quota
    with _lock:
        if _quota is None:
            _quota = DailyQuota(lambda: get_settings().GEMINI_REQUESTS_PER_DAY)
        return _quota


def consistency_should_run() -> tuple[bool, str | None]:
    """Skip the consistency run when fewer than 20% of today's Gemini quota remains."""
    if get_settings().LLM_PROVIDER != "gemini":
        return True, None
    try:
        if get_quota().remaining_fraction() < 0.20:
            return False, "skipped to save the daily AI quota"
    except Exception:  # noqa: BLE001 - never block an analysis because of bookkeeping
        log.exception("quota check failed")
    return True, None


def reset_for_tests() -> None:
    global _pacer, _quota
    with _lock:
        _pacer = None
        _quota = None
