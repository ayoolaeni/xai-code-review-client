"""Retention job (Section 12.9, NFR6): every 15 minutes and once at startup."""

from __future__ import annotations

import datetime as dt
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.db import SessionLocal
from app.models import AnalysisReport, Submission
from app.services import settings_service

log = logging.getLogger(__name__)

STUCK_AFTER = dt.timedelta(minutes=30)
STUCK_MESSAGE = "The analysis took too long and was stopped. Please try again."

_scheduler: BackgroundScheduler | None = None


def run_retention(now: dt.datetime | None = None) -> dict[str, int]:
    """Delete expired guest data and clean up jobs stuck in queued/running. Returns counts."""
    now = now or dt.datetime.now(dt.UTC)
    deleted_guests = stuck_failed = stuck_deleted = 0
    with SessionLocal() as db:
        hours = settings_service.get_value(db, "guest_retention_hours")
        cutoff = now - dt.timedelta(hours=hours)
        # 1. Stuck jobs: mark failed first; guest ones are deleted together with their submission.
        stuck_cutoff = now - STUCK_AFTER
        stuck = db.execute(
            select(AnalysisReport, Submission)
            .join(Submission, AnalysisReport.submission_id == Submission.submission_id)
            .where(
                AnalysisReport.status.in_(("queued", "running")),
                AnalysisReport.created_at < stuck_cutoff,
            )
        ).all()
        for report, sub in stuck:
            report.status = "failed"
            report.stage = "completed"
            report.error_message = STUCK_MESSAGE
            stuck_failed += 1
            if sub.user_id is None:
                db.delete(sub)
                stuck_deleted += 1
        db.commit()
        # 2. Expired guest submissions (reports, findings, feedback cascade).
        expired = db.scalars(
            select(Submission).where(Submission.user_id.is_(None), Submission.submitted_at < cutoff)
        ).all()
        for sub in expired:
            db.delete(sub)
            deleted_guests += 1
        db.commit()
    counts = {
        "guest_deleted": deleted_guests,
        "stuck_failed": stuck_failed,
        "stuck_deleted": stuck_deleted,
    }
    log.info(
        "retention job finished: %s",
        counts,
        extra={"event": "retention", "count": deleted_guests},
    )
    return counts


def _safe_run() -> None:
    try:
        run_retention()
    except Exception:  # noqa: BLE001 - the scheduler must keep running
        log.exception("retention job failed")


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _safe_run()  # once at startup
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _safe_run,
        "interval",
        minutes=15,
        id="retention",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
