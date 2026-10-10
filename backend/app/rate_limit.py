"""Rate limiting with slowapi (Section 7.3)."""

from __future__ import annotations

import time

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.db import SessionLocal
from app.errors import error_body
from app.security import COOKIE_NAME, client_ip, decode_token

DEFAULT_LIMIT = "120/minute"
AUTH_LIMIT = "10/15minutes"


def ip_key(request: Request) -> str:
    return "ip:" + client_ip(request)


def analysis_key(request: Request) -> str:
    """Logged-in users are limited per user ID, guests per IP address."""
    token = request.cookies.get(COOKIE_NAME)
    payload = decode_token(token) if token else None
    if payload and payload.get("sub"):
        return "user:" + str(payload["sub"])
    return ip_key(request)


def analysis_limit(key: str) -> str:
    """Dynamic limit read from admin settings at request time."""
    from app.services import settings_service

    with SessionLocal() as db:
        values = settings_service.get(db)
    if key.startswith("user:"):
        return f"{values['user_rate_limit_per_hour']}/hour"
    return f"{values['guest_rate_limit_per_hour']}/hour"


limiter = Limiter(key_func=ip_key, default_limits=[DEFAULT_LIMIT], headers_enabled=False)


def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = 60
    try:
        limit_item, keys = (
            request.state.view_rate_limit[0],
            request.state.view_rate_limit[1],
        )
        reset_at, _remaining = limiter.limiter.get_window_stats(limit_item, *keys)
        retry_after = max(1, int(reset_at - time.time()))
    except Exception:  # noqa: BLE001 - the header is best effort
        pass
    minutes = max(1, round(retry_after / 60))
    message = (
        "You have made too many requests. "
        f"Please wait about {minutes} minute{'s' if minutes != 1 else ''} and try again."
    )
    return JSONResponse(
        status_code=429,
        content=error_body("RATE_LIMITED", message, {"retry_after_seconds": retry_after}),
        headers={"Retry-After": str(retry_after)},
    )
