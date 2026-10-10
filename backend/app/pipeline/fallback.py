"""Static-only fallback texts (Sections 8.9.6 and 8.19, NFR7)."""

from __future__ import annotations

import datetime as dt

PURPOSE = "The AI explanation is not available for this analysis. The findings below come from static analysis tools only."
STATIC_ONLY = "This report shows static analysis results only."

_MESSAGES = {
    "rate_limit": f"The AI service is busy. {STATIC_ONLY} Please try again in a minute.",
    "timeout": f"The AI service did not answer in time. {STATIC_ONLY} Please try again in a minute.",
    "auth": f"The AI service is not configured correctly. {STATIC_ONLY}",
    "not_configured": f"The AI service is not configured. {STATIC_ONLY}",
    "model_not_found": f"The configured AI model is not available. {STATIC_ONLY}",
    "blocked": f"The AI service declined to analyse this code. {STATIC_ONLY}",
    "invalid_output": f"The AI service did not return a usable explanation after several attempts. {STATIC_ONLY}",
    "api_error": f"The AI service returned an error. {STATIC_ONLY} Please try again later.",
}


def _wat_time(until_utc: dt.datetime) -> str:
    """Format the reset time in West Africa Time (UTC+1), e.g. '8:00 a.m.'."""
    wat = until_utc.astimezone(dt.timezone(dt.timedelta(hours=1)))
    hour = wat.hour % 12 or 12
    suffix = "a.m." if wat.hour < 12 else "p.m."
    return f"{hour}:{wat.minute:02d} {suffix}"


def message(reason: str | None, until_utc: dt.datetime | None = None) -> str:
    if reason == "quota_exhausted":
        when = f" ({_wat_time(until_utc)} West Africa Time)" if until_utc else ""
        return (
            f"The free AI quota for today has been used up. {STATIC_ONLY} The AI explanation will be available "
            f"again after midnight Pacific time{when}."
        )
    return _MESSAGES.get(reason or "api_error", _MESSAGES["api_error"])
