"""Build the report JSON of Section 9 from the database."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalysisReport, Feedback, User
from app.pipeline import fallback, taxonomy
from app.pipeline.language import LABELS
from app.pipeline.review_rule import NO_REVIEW_MESSAGE
from app.pipeline.verify_improved import has_problems
from app.services import settings_service
from app.time_utils import as_utc

DATA_USE_NOTICE = "AI service: Google Gemini (free tier). On the free tier, Google may use submitted code to improve its products."
CHECKED = [
    "Security weaknesses",
    "Reliability problems",
    "Performance problems",
    "Maintainability problems",
    "Hard-coded secrets",
]
NOT_CHECKED = [
    "Runtime behaviour (the code was never executed)",
    "Other files and dependencies",
    "Business logic correctness against your requirements",
]
NOT_STORED_NOTE = "The original code was not stored (you chose not to keep it)."


def _counts(findings) -> dict:
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        counts[f.severity] += 1
    counts["total"] = len(findings)
    return counts


def _feedback_for(db: Session, report: AnalysisReport, user: User | None, token: str | None) -> dict:
    row = None
    if user is not None:
        row = db.scalar(
            select(Feedback).where(Feedback.report_id == report.report_id, Feedback.user_id == user.user_id)
        )
    if row is None and token:
        row = db.scalar(
            select(Feedback).where(Feedback.report_id == report.report_id, Feedback.feedback_token == token)
        )
    if row is None:
        return {"rating": None, "was_helpful": None, "comment": None}
    return {
        "rating": row.rating,
        "was_helpful": row.was_helpful,
        "comment": row.comment,
    }


def build_report(
    db: Session,
    report: AnalysisReport,
    viewer: User | None = None,
    feedback_token: str | None = None,
) -> dict:
    sub = report.submission
    owner = "user" if sub.user_id is not None else "guest"
    expires_at = None
    if owner == "guest":
        hours = settings_service.get_value(db, "guest_retention_hours")
        expires_at = as_utc(sub.submitted_at) + dt.timedelta(hours=hours)

    findings = list(report.findings)
    improved = report.improved_version
    check = report.improved_code_check
    ai_available = bool(report.ai_explanation_available)
    limitations = list(report.limitations_note or [])
    ai_message = None
    if not ai_available:
        ai_message = next((n for n in limitations if fallback.STATIC_ONLY in n), None) or fallback.message(
            report.ai_unavailable_reason, as_utc(report.ai_unavailable_until)
        )
    reasons = list(report.review_reasons or [])
    code_stored = sub.code_text is not None

    return {
        "public_id": report.public_id,
        "status": "completed",
        "created_at": as_utc(report.created_at),
        "completed_at": as_utc(report.completed_at),
        "processing_time_ms": report.processing_time_ms,
        "expires_at": expires_at,
        "owner": owner,
        "submission": {
            "language": sub.language,
            "language_label": LABELS.get(sub.language, sub.language),
            "language_source": sub.language_source,
            "filename": sub.filename,
            "line_count": sub.line_count,
            "code_stored": code_stored,
            "original_code": sub.code_text,
            "redacted_code": report.redacted_code,
        },
        "overview": {
            "purpose_summary": report.purpose_summary or fallback.PURPOSE,
            "overall_risk_level": report.overall_risk_level or "NONE",
            "overall_confidence": report.overall_confidence or "LOW",
            "human_review_advised": bool(report.human_review_advised),
            "review_reasons": reasons,
            "no_review_message": None if reasons else NO_REVIEW_MESSAGE,
            "ai_explanation_available": ai_available,
            "ai_unavailable_reason": report.ai_unavailable_reason,
            "ai_unavailable_message": ai_message,
            "ai_unavailable_until": as_utc(report.ai_unavailable_until),
            "counts": _counts(findings),
            "sensitive_domains": list(report.sensitive_domains or []),
        },
        "breakdown": [
            {
                "start_line": s.start_line,
                "end_line": s.end_line,
                "title": s.title,
                "explanation": s.explanation,
            }
            for s in report.sections
        ],
        "findings": [
            {
                "key": f.public_key,
                "category": f.category,
                "title": f.title,
                "description": f.description,
                "evidence": f.evidence or None,
                "recommendation": f.recommendation,
                "start_line": f.start_line,
                "end_line": f.end_line,
                "severity": f.severity,
                "confidence": f.confidence,
                "confidence_reason": f.confidence_reason,
                "cwe": taxonomy.cwe_info(f.cwe_id),
                "owasp_category": f.owasp_category,
                "source": f.source,
                "static_tool": f.static_tool,
                "static_rule_id": f.static_rule_id,
                "ai_assessment": f.ai_assessment,
            }
            for f in findings
        ],
        "improved": {
            "available": improved is not None,
            "improved_code": improved.improved_code if improved else None,
            "changes": list(improved.change_reasons) if improved else [],
            "check": check,
            "requires_acknowledgement": improved is not None
            and any(f.severity == "CRITICAL" for f in findings),
            "has_problems": has_problems(check),
        },
        "transparency": {
            "model_name": report.model_name,
            "llm_provider": report.llm_provider,
            "data_use_notice": (DATA_USE_NOTICE if report.llm_provider == "gemini" else None),
            "prompt_version": report.prompt_version,
            "llm_requests": report.llm_requests or 0,
            "tools_run": list(report.tools_run or []),
            "redaction": {
                "count": report.redaction_count or 0,
                "by_type": dict(report.redaction_by_type or {}),
            },
            "consistency": report.consistency
            or {
                "enabled": False,
                "run_b_ok": None,
                "matched": 0,
                "only_in_a": 0,
                "only_in_b": 0,
                "reason": None,
            },
            "checked": CHECKED,
            "not_checked": NOT_CHECKED,
            "limitations": limitations,
            "code_executed": False,
            "processing_time_ms": report.processing_time_ms,
            "code_storage_note": (
                None
                if code_stored
                else (
                    f"{NOT_STORED_NOTE} The comparison uses the version with secrets masked, which was kept "
                    "so the report still works."
                )
            ),
        },
        "feedback": _feedback_for(db, report, viewer, feedback_token),
    }
