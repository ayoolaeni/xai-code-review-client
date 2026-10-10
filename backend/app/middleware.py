"""HTTP middleware: request IDs, security headers, CSRF checks, HTTPS redirect (Section 12)."""

from __future__ import annotations

import logging
import time
import uuid
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import get_settings
from app.errors import error_body

log = logging.getLogger("app.http")

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "worker-src 'self' blob:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
)
STATE_CHANGING = {"POST", "PUT", "PATCH", "DELETE"}


def _origin_of(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}".lower()


def install_middleware(app: FastAPI) -> None:
    settings = get_settings()

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        start = time.perf_counter()
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        path = request.url.path

        # HTTP → HTTPS redirect behind the platform proxy (production only).
        if settings.is_production and request.headers.get("x-forwarded-proto") == "http":
            url = request.url.replace(scheme="https")
            return RedirectResponse(str(url), status_code=307)

        if path.startswith("/api/") and request.method in STATE_CHANGING:
            # CSRF defence 1: reject "simple" cross-site form posts. JSON bodies are required.
            content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type and content_type != "application/json":
                return JSONResponse(
                    status_code=415,
                    content=error_body(
                        "UNSUPPORTED_MEDIA_TYPE",
                        "Requests must be sent as JSON (Content-Type: application/json).",
                    ),
                )
            # CSRF defence 2 (production): Origin / Referer must match the site.
            if settings.is_production:
                expected = _origin_of(settings.APP_BASE_URL)
                origin = request.headers.get("origin")
                referer = request.headers.get("referer")
                actual = origin.lower() if origin else (_origin_of(referer) if referer else None)
                if actual != expected:
                    return JSONResponse(
                        status_code=403,
                        content=error_body("FORBIDDEN", "Cross-site request rejected."),
                    )

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
            log.info(
                "request",
                extra={
                    "event": "http_request",
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": int((time.perf_counter() - start) * 1000),
                    "request_id": request_id,
                },
            )
        return response
