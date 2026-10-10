"""Health and metadata endpoints (Section 7.2 — Meta)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.llm import health as llm_health
from app.services import settings_service
from app.static_analysis import registry

router = APIRouter(prefix="/api", tags=["meta"])

LANGUAGES = [
    {"id": "python", "label": "Python", "extensions": [".py"]},
    {"id": "javascript", "label": "JavaScript", "extensions": [".js", ".mjs", ".cjs"]},
    {"id": "java", "label": "Java", "extensions": [".java"]},
]


def privacy_notice(retention_hours: int) -> str:
    s = get_settings()
    if s.LLM_PROVIDER == "gemini":
        sent_to = (
            "Your code is sent to the Google Gemini AI service (free tier) for analysis. On the free tier, "
            "Google may use submitted code to improve its products, so do not paste passwords, secret keys "
            "or confidential code."
        )
    elif s.LLM_PROVIDER == "mock":
        sent_to = (
            "This server uses an offline demonstration AI, so your code does not leave the server. "
            "Do not paste passwords, secret keys or confidential code."
        )
    else:
        sent_to = (
            f"Your code is sent to an external AI service ({s.LLM_PROVIDER}) for analysis, so do not paste "
            "passwords, secret keys or confidential code."
        )
    return (
        f"{sent_to} Detected secrets are masked automatically. "
        f"Guest reports are deleted after {retention_hours} hours."
    )


@router.get("/health")
def health(request: Request, db: Session = Depends(get_db)):
    s = get_settings()
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # noqa: BLE001
        db_status = "error"
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "llm_provider": s.LLM_PROVIDER,
        "llm_model": s.LLM_MODEL if s.LLM_PROVIDER != "mock" else "mock-v1",
        "llm": llm_health.llm_status(),
        "llm_quota_today": llm_health.quota_today(),
        "tools": registry.tool_availability(),
    }


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    values = settings_service.get(db)
    return {
        "languages": LANGUAGES,
        "max_lines": values["max_lines"],
        "max_chars": values["max_chars"],
        "guest_retention_hours": values["guest_retention_hours"],
        "privacy_notice": privacy_notice(values["guest_retention_hours"]),
        "llm_provider": get_settings().LLM_PROVIDER,
    }
