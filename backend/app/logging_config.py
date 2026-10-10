"""Logging setup: JSON lines in production, readable text in development (Section 15)."""

from __future__ import annotations

import json
import logging
import sys

from app.config import get_settings

EXTRA_FIELDS = (
    "event",
    "public_id",
    "stage",
    "duration_ms",
    "tool",
    "status",
    "llm_attempts",
    "llm_latency_ms",
    "tokens_in",
    "tokens_out",
    "method",
    "path",
    "request_id",
    "count",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in EXTRA_FIELDS:
            if hasattr(record, field):
                data[field] = getattr(record, field)
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = {f: getattr(record, f) for f in EXTRA_FIELDS if hasattr(record, f)}
        if extras:
            base += "  " + " ".join(f"{k}={v}" for k, v in extras.items())
        return base


_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    s = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    if s.is_production:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(s.LOG_LEVEL.upper())
    # Quieten chatty libraries.
    for name in ("httpx", "httpcore", "google_genai", "apscheduler", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
    _configured = True
