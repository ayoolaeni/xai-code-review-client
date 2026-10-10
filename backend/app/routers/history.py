"""Registered users' analysis history (FR15)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AnalysisReport, Submission, User
from app.security import require_user
from app.time_utils import as_utc

router = APIRouter(prefix="/api", tags=["history"])


def _preview(text: str | None) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= 140 else text[:139].rstrip() + "…"


@router.get("/history")
def history(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    language: str = Query("", max_length=20),
    q: str = Query("", max_length=200),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Submission, AnalysisReport)
        .join(AnalysisReport, AnalysisReport.submission_id == Submission.submission_id)
        .where(Submission.user_id == user.user_id)
    )
    if language:
        stmt = stmt.where(Submission.language == language)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(AnalysisReport.purpose_summary).like(like),
                func.lower(Submission.filename).like(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(Submission.submitted_at.desc(), Submission.submission_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "public_id": report.public_id,
            "submitted_at": as_utc(sub.submitted_at),
            "language": sub.language,
            "filename": sub.filename,
            "line_count": sub.line_count,
            "status": report.status,
            "overall_risk_level": report.overall_risk_level,
            "overall_confidence": report.overall_confidence,
            "human_review_advised": report.human_review_advised,
            "purpose_summary_preview": _preview(report.purpose_summary),
        }
        for sub, report in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
