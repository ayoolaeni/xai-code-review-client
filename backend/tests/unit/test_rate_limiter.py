"""Free-tier pacer and daily quota (Section 8.9.6)."""

import datetime as dt

import pytest

from app.llm import rate_limiter
from app.llm.client import LLMError
from app.llm.rate_limiter import DailyQuota, RequestPacer
from app.time_utils import next_pacific_midnight_utc, pacific_day


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.slept = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        self.slept += seconds


def test_pacer_blocks_the_extra_request_within_60s():
    clock = FakeClock()
    pacer = RequestPacer(8, clock=clock, sleep=clock.sleep)
    for _ in range(8):
        assert pacer.acquire() == 0
    assert not pacer.try_acquire()  # the 9th within 60 s is refused
    clock.now += 30
    waited = pacer.acquire()  # the 9th now waits for the oldest to leave the window
    assert 29 <= waited <= 31
    # All 8 earlier requests happened at the same instant, so they left the window together.
    assert pacer.in_window() == 1


def test_pacer_raises_after_max_wait():
    clock = FakeClock()
    pacer = RequestPacer(1, clock=clock, sleep=clock.sleep, max_wait=10)
    pacer.acquire()
    with pytest.raises(LLMError) as e:
        pacer.acquire()
    assert e.value.kind == "rate_limit"


def test_daily_counter_stops_calls_at_limit(db):
    now = dt.datetime(2026, 10, 7, 12, 0, tzinfo=dt.UTC)
    quota = DailyQuota(lambda: 3, now=lambda: now)
    for _ in range(3):
        quota.check()
        quota.record(10, 5)
    assert quota.used_today() == 3
    assert quota.usage_today() == {
        "requests": 3,
        "input_tokens": 30,
        "output_tokens": 15,
    }
    with pytest.raises(LLMError) as e:
        quota.check()
    assert e.value.kind == "quota_exhausted"


def test_exhaust_today_sets_counter_to_limit(db):
    now = dt.datetime(2026, 10, 7, 12, 0, tzinfo=dt.UTC)
    quota = DailyQuota(lambda: 50, now=lambda: now)
    quota.record()
    quota.exhaust_today()
    assert quota.used_today() == 50


def test_pacific_day_boundary(db):
    # 07:59 UTC on 8 Oct is still 7 Oct in Los Angeles (PDT = UTC-7); 08:00 UTC is 8 Oct.
    before = dt.datetime(2026, 10, 8, 6, 59, tzinfo=dt.UTC)
    after = dt.datetime(2026, 10, 8, 7, 0, tzinfo=dt.UTC)
    assert pacific_day(before) == dt.date(2026, 10, 7)
    assert pacific_day(after) == dt.date(2026, 10, 8)
    current = {"now": before}
    quota = DailyQuota(lambda: 2, now=lambda: current["now"])
    quota.record()
    quota.record()
    with pytest.raises(LLMError):
        quota.check()
    current["now"] = after  # new Pacific day → quota available again
    quota.check()
    assert next_pacific_midnight_utc(before) == after


def test_20_percent_rule_disables_consistency(db, monkeypatch, settings):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_REQUESTS_PER_DAY", 10)
    quota = rate_limiter.get_quota()
    for _ in range(8):
        quota.record()
    assert rate_limiter.consistency_should_run() == (True, None)  # exactly 20% left
    quota.record()
    run, reason = rate_limiter.consistency_should_run()
    assert run is False and reason == "skipped to save the daily AI quota"


def test_consistency_always_runs_for_mock(db, monkeypatch, settings):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    assert rate_limiter.consistency_should_run() == (True, None)
