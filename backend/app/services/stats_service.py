"""Usage statistics for administrators (Section 14). Guest data already deleted is not counted."""

from __future__ import annotations

import datetime as dt
import math
from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm.rate_limiter import get_quota
from app.models import AnalysisReport, Feedback, Finding, Submission, User
from app.time_utils import as_utc


def _p90(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)]


def compute(db: Session, days: int) -> dict:
    now = dt.datetime.now(dt.UTC)
    since = now - dt.timedelta(days=days)
    rows = db.execute(
        select(Submission, AnalysisReport)
        .join(AnalysisReport, AnalysisReport.submission_id == Submission.submission_id)
        .where(Submission.submitted_at >= since)
    ).all()

    per_day: Counter[str] = Counter()
    by_language: Counter[str] = Counter()
    times: list[int] = []
    completed = failed = fallback = guests = review_advised = 0
    tool_failures: dict[str, int] = defaultdict(int)
    report_ids: list[int] = []
    for sub, rep in rows:
        report_ids.append(rep.report_id)
        per_day[as_utc(sub.submitted_at).date().isoformat()] += 1
        by_language[sub.language] += 1
        if sub.user_id is None:
            guests += 1
        if rep.status == "completed":
            completed += 1
            if rep.processing_time_ms is not None:
                times.append(rep.processing_time_ms)
            if rep.ai_explanation_available is False:
                fallback += 1
            if rep.human_review_advised:
                review_advised += 1
        elif rep.status == "failed":
            failed += 1
        for run in rep.tools_run or []:
            if run.get("status") in ("failed", "timeout"):
                tool_failures[run.get("tool", "?")] += 1

    # Every day in the range, including days without analyses.
    days_list = [(since + dt.timedelta(days=i + 1)).date().isoformat() for i in range(days)]
    findings_by_severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    findings_by_source = {"static": 0, "llm": 0, "both": 0}
    if report_ids:
        for sev, n in db.execute(
            select(Finding.severity, func.count())
            .where(Finding.report_id.in_(report_ids))
            .group_by(Finding.severity)
        ):
            findings_by_severity[sev] = n
        for src, n in db.execute(
            select(Finding.source, func.count())
            .where(Finding.report_id.in_(report_ids))
            .group_by(Finding.source)
        ):
            findings_by_source[src] = n

    feedback_rows = db.scalars(select(Feedback).where(Feedback.created_at >= since)).all()
    fb_count = len(feedback_rows)

    quota = get_quota()
    usage_today = quota.usage_today()
    return {
        "range_days": days,
        "totals": {
            "analyses": len(rows),
            "completed": completed,
            "failed": failed,
            "fallback": fallback,
            "registered_users": db.scalar(select(func.count(User.user_id))) or 0,
            "guest_analyses": guests,
        },
        "per_day": [{"date": d, "analyses": per_day.get(d, 0)} for d in days_list],
        "by_language": {lang: by_language.get(lang, 0) for lang in ("python", "javascript", "java")},
        "avg_processing_ms": int(sum(times) / len(times)) if times else None,
        "p90_processing_ms": _p90(times),
        "findings_by_severity": findings_by_severity,
        "findings_by_source": findings_by_source,
        "human_review_advised_rate": ((review_advised / completed) if completed else None),
        "feedback": {
            "count": fb_count,
            "avg_rating": ((sum(f.rating for f in feedback_rows) / fb_count) if fb_count else None),
            "helpful_rate": (
                (sum(1 for f in feedback_rows if f.was_helpful) / fb_count) if fb_count else None
            ),
        },
        "tool_failures": {
            tool: tool_failures.get(tool, 0) for tool in ("semgrep", "bandit", "eslint", "pmd")
        },
        "llm_usage_today": {
            "requests": usage_today["requests"],
            "limit": get_settings().GEMINI_REQUESTS_PER_DAY,
            "input_tokens": usage_today["input_tokens"],
            "output_tokens": usage_today["output_tokens"],
        },
        "llm_usage_history": quota.history(30),
    }
