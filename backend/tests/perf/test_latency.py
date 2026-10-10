"""NFR1 performance test (Section 16.5) — run manually with the real provider:

    LLM_PROVIDER=gemini GEMINI_API_KEY=... python -m pytest -m perf tests/perf -s

It analyses the benchmark samples (padded to ≥ 100 lines with realistic helper code) and a generated
200-line file, 5 times each, and reports median and p90 `processing_time_ms`. Time spent waiting for a free-tier
request slot (the pacer) is measured separately. Pass: p90 ≤ 60 000 ms. Results: evaluation/results/performance.csv.
"""

from __future__ import annotations

import csv
import statistics
import time

import pytest

from app.config import get_settings
from app.db import Base, SessionLocal, init_db
from app.llm import rate_limiter
from app.pipeline.orchestrator import run_pipeline_for_code
from app.seed import seed
from tests.conftest import BENCHMARK_DIR, REPO_ROOT

pytestmark = pytest.mark.perf

RUNS = 5
TARGET_P90_MS = 60_000

PYTHON_PADDING = '''

def _format_currency(amount, currency="NGN"):
    """Format an amount of money for display."""
    return f"{currency} {amount:,.2f}"


def _chunk(items, size):
    """Split a list into chunks of the given size."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def _safe_ratio(numerator, denominator):
    """Divide two numbers, returning 0 when the denominator is 0."""
    if denominator == 0:
        return 0.0
    return numerator / denominator
'''


def generated_200_line_file() -> str:
    lines = ['"""Generated reporting helpers used for the latency test."""', "", "import statistics", ""]
    i = 0
    while len(lines) < 196:
        lines += [
            f"def metric_{i}(values):",
            f'    """Summary statistic number {i}."""',
            "    if not values:",
            "        return 0.0",
            f"    return statistics.mean(values) * {i + 1}",
            "",
        ]
        i += 1
    return "\n".join(lines[:200])


def padded(code: str, language: str) -> str:
    if code.count("\n") + 1 >= 100 or language != "python":
        return code
    while code.count("\n") + 1 < 100:
        code += PYTHON_PADDING
    return code


def p90(values: list[int]) -> int:
    ordered = sorted(values)
    return ordered[max(0, int(round(0.9 * len(ordered))) - 1)]


def test_latency(tmp_path):
    if get_settings().LLM_PROVIDER == "mock":
        pytest.skip("Run with LLM_PROVIDER=gemini (the mock provider is not representative)")
    engine = init_db(f"sqlite:///{(tmp_path / 'perf.db').as_posix()}")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)

    samples = [("generated_200.py", "python", generated_200_line_file())]
    for path in sorted((BENCHMARK_DIR / "samples").iterdir())[:10]:
        language = {"py": "python", "js": "javascript", "java": "java"}[path.suffix[1:]]
        samples.append((path.name, language, padded(path.read_text(encoding="utf-8"), language)))

    pacer = rate_limiter.get_pacer()
    original_acquire = pacer.acquire
    waited: list[float] = []

    def timed_acquire():
        w = original_acquire()
        waited.append(w)
        return w

    pacer.acquire = timed_acquire  # measure time spent waiting for a free request slot
    rows = []
    try:
        for name, language, code in samples:
            for run in range(1, RUNS + 1):
                waited.clear()
                t0 = time.monotonic()
                report = run_pipeline_for_code(code, language, name)
                wall = int((time.monotonic() - t0) * 1000)
                wait_ms = int(sum(waited) * 1000)
                rows.append(
                    {
                        "sample": name,
                        "run": run,
                        "lines": code.count("\n") + 1,
                        "processing_time_ms": report["processing_time_ms"],
                        "wall_ms": wall,
                        "pacer_wait_ms": wait_ms,
                        "processing_minus_wait_ms": report["processing_time_ms"] - wait_ms,
                        "ai_available": report["overview"]["ai_explanation_available"],
                    }
                )
                print(rows[-1])
    finally:
        pacer.acquire = original_acquire

    out = REPO_ROOT / "evaluation" / "results" / "performance.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    processing = [r["processing_minus_wait_ms"] for r in rows]
    print(
        f"\nmedian {statistics.median(processing):.0f} ms, p90 {p90(processing)} ms "
        f"(excluding free-tier queueing); results in {out}"
    )
    assert p90(processing) <= TARGET_P90_MS
