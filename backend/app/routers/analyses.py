"""Analysis endpoints (FR1–FR13)."""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError, not_found
from app.models import AnalysisReport, Feedback, User
from app.pipeline.stages import STAGE_COUNT, STAGE_INDEX, STAGE_LABEL
from app.rate_limit import analysis_key, analysis_limit, limiter
from app.schemas import (
    AnalysisCreate,
    AnalysisCreated,
    AnalysisStatus,
    FeedbackIn,
    FeedbackOut,
)
from app.security import client_ip, get_current_user_optional, hash_ip
from app.services import analysis_service, pdf_service, report_service, settings_service
from app.services.analysis_service import JobRunner, get_job_runner
from app.time_utils import as_utc

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


def load_report_for_viewer(db: Session, public_id: str, user: User | None) -> AnalysisReport:
    """Guest reports: anyone with the UUID. Owned reports: owner or admin only (404 otherwise)."""
    report = db.query(AnalysisReport).filter_by(public_id=public_id).one_or_none()
    if report is None:
        raise not_found()
    sub = report.submission
    if sub.user_id is not None:
        if user is None or (user.user_id != sub.user_id and user.role != "admin"):
            raise not_found()
    else:
        hours = settings_service.get_value(db, "guest_retention_hours")
        if as_utc(sub.submitted_at) + dt.timedelta(hours=hours) < dt.datetime.now(dt.UTC):
            raise not_found()
    return report


def status_of(report: AnalysisReport, runner: JobRunner) -> AnalysisStatus:
    stage = report.stage or "validating"
    return AnalysisStatus(
        public_id=report.public_id,
        status=report.status,
        stage=stage,
        stage_label=STAGE_LABEL.get(stage, stage),
        stage_index=STAGE_INDEX.get(stage, 1),
        stage_count=STAGE_COUNT,
        queue_position=(runner.queue_position(report.public_id) if report.status == "queued" else None),
        started_at=as_utc(report.started_at),
        error_message=report.error_message,
    )


@router.post("", status_code=202, response_model=AnalysisCreated)
@limiter.limit(analysis_limit, key_func=analysis_key)
def create(
    request: Request,
    body: AnalysisCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
    runner: JobRunner = Depends(get_job_runner),
):
    report = analysis_service.create_analysis(db, body, user, hash_ip(client_ip(request)))
    runner.submit(report.public_id)
    return AnalysisCreated(public_id=report.public_id, status="queued")


@router.get("/{public_id}")
def get_analysis(
    public_id: str,
    request: Request,
    ft: str | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
    runner: JobRunner = Depends(get_job_runner),
):
    """AnalysisStatus while queued/running/failed, the full Report (Section 9) when completed."""
    report = load_report_for_viewer(db, public_id, user)
    if report.status == "completed":
        return report_service.build_report(db, report, user, ft)
    return status_of(report, runner)


@router.get("/{public_id}/pdf")
def download_pdf(
    public_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """The full report as a PDF (FR12)."""
    report = load_report_for_viewer(db, public_id, user)
    if report.status != "completed":
        raise AppError(
            409,
            "REPORT_NOT_READY",
            "The report is not ready yet. Please wait until the analysis finishes.",
        )
    pdf = pdf_service.render_pdf(report_service.build_report(db, report, user))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="xai-report-{public_id[:8]}.pdf"'},
    )


@router.post("/{public_id}/feedback", response_model=FeedbackOut)
def submit_feedback(
    public_id: str,
    request: Request,
    body: FeedbackIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Upsert one rating per (report, user) — or per (report, browser token) for guests (FR13)."""
    report = load_report_for_viewer(db, public_id, user)
    if report.status != "completed":
        raise AppError(
            409,
            "REPORT_NOT_READY",
            "You can rate the explanation once the report is ready.",
        )
    comment = (body.comment or "").strip() or None
    row = None
    token = None
    if user is not None:
        row = db.scalar(
            select(Feedback).where(Feedback.report_id == report.report_id, Feedback.user_id == user.user_id)
        )
    else:
        token = body.feedback_token or str(uuid.uuid4())
        row = db.scalar(
            select(Feedback).where(Feedback.report_id == report.report_id, Feedback.feedback_token == token)
        )
    if row is None:
        row = Feedback(
            report_id=report.report_id,
            user_id=user.user_id if user else None,
            feedback_token=token,
        )
        db.add(row)
    row.rating = body.rating
    row.was_helpful = body.was_helpful
    row.comment = comment
    db.commit()
    db.refresh(row)
    return FeedbackOut(feedback_id=row.feedback_id, feedback_token=row.feedback_token)


@router.delete("/{public_id}", status_code=204)
def delete_analysis(
    public_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    report = load_report_for_viewer(db, public_id, user)
    # Only the owner or an admin may delete; guest reports cannot be deleted by anonymous users.
    if user is None or (report.submission.user_id != user.user_id and user.role != "admin"):
        raise not_found()
    db.delete(report.submission)
    db.commit()
    return Response(status_code=204)
