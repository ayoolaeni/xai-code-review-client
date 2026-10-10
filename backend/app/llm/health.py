"""LLM status for /api/health (Section 7.2)."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.llm.client import get_llm_client
from app.llm.rate_limiter import get_quota

log = logging.getLogger(__name__)


def llm_status() -> str:
    """ok | not_configured | model_not_found | quota_exhausted | error"""
    s = get_settings()
    if s.LLM_PROVIDER == "mock":
        return "ok"
    if not s.llm_configured:
        return "not_configured"
    try:
        if s.LLM_PROVIDER == "gemini":
            quota = get_quota()
            if quota.used_today() >= quota.limit:
                return "quota_exhausted"
            client = get_llm_client()
            status = client.check_model()  # type: ignore[attr-defined]  (cached 10 minutes)
            return {"auth": "not_configured", "api_error": "error"}.get(status, status)
    except Exception:  # noqa: BLE001 - health must never fail
        log.exception("LLM health check failed")
        return "error"
    return "ok"


def quota_today() -> dict:
    s = get_settings()
    try:
        used = get_quota().used_today()
    except Exception:  # noqa: BLE001
        used = 0
    return {"used": used, "limit": s.GEMINI_REQUESTS_PER_DAY}
