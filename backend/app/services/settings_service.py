"""Admin-editable settings stored in `system_settings` (Section 6.8), cached for 30 s."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.models import SystemSetting, utcnow

CACHE_TTL_SECONDS = 30
TOOL_REGISTRY: dict[str, list[str]] = {
    "python": ["semgrep", "bandit"],
    "javascript": ["semgrep", "eslint"],
    "java": ["semgrep", "pmd"],
}


@dataclass(frozen=True)
class SettingDef:
    key: str
    type: str  # int | float | bool | tools
    description: str
    min: float | None = None
    max: float | None = None

    def default(self) -> Any:
        s = get_settings()
        return {
            "max_lines": s.DEFAULT_MAX_LINES,
            "max_chars": s.DEFAULT_MAX_CHARS,
            "guest_retention_hours": s.DEFAULT_GUEST_RETENTION_HOURS,
            "guest_rate_limit_per_hour": s.DEFAULT_GUEST_RATE_LIMIT_PER_HOUR,
            "user_rate_limit_per_hour": s.DEFAULT_USER_RATE_LIMIT_PER_HOUR,
            "consistency_check_enabled": s.DEFAULT_CONSISTENCY_CHECK_ENABLED,
            "enabled_tools": {lang: list(tools) for lang, tools in TOOL_REGISTRY.items()},
            "llm_temperature": s.LLM_TEMPERATURE,
        }[self.key]


DEFINITIONS: dict[str, SettingDef] = {
    d.key: d
    for d in [
        SettingDef(
            "max_lines",
            "int",
            "Maximum number of lines a submission may have.",
            20,
            2000,
        ),
        SettingDef(
            "max_chars",
            "int",
            "Maximum number of characters a submission may have.",
            1000,
            200000,
        ),
        SettingDef(
            "guest_retention_hours",
            "int",
            "Hours before guest submissions and reports are deleted.",
            1,
            168,
        ),
        SettingDef(
            "guest_rate_limit_per_hour",
            "int",
            "Analyses a guest (per IP address) may start per hour.",
            1,
            1000,
        ),
        SettingDef(
            "user_rate_limit_per_hour",
            "int",
            "Analyses a registered user may start per hour.",
            1,
            1000,
        ),
        SettingDef(
            "consistency_check_enabled",
            "bool",
            "Run a second, independent AI review to check consistency (uses one extra AI request).",
        ),
        SettingDef(
            "enabled_tools",
            "tools",
            "Static analysis tools run for each language (subset of the registry).",
        ),
        SettingDef(
            "llm_temperature",
            "float",
            "Randomness of the AI model (lower = more predictable).",
            0.0,
            1.0,
        ),
    ]
}

_lock = threading.Lock()
_cache: dict[str, Any] | None = None
_cache_time = 0.0


def invalidate_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def seed_defaults(db: Session) -> None:
    existing = set(db.scalars(select(SystemSetting.key)).all())
    for key, d in DEFINITIONS.items():
        if key not in existing:
            db.add(SystemSetting(key=key, value=d.default()))
    db.commit()
    invalidate_cache()


def get(db: Session) -> dict[str, Any]:
    """All settings as a dict (cached for 30 s)."""
    global _cache, _cache_time
    with _lock:
        if _cache is not None and time.monotonic() - _cache_time < CACHE_TTL_SECONDS:
            return dict(_cache)
    values = {key: d.default() for key, d in DEFINITIONS.items()}
    for row in db.scalars(select(SystemSetting)).all():
        if row.key in DEFINITIONS:
            values[row.key] = row.value
    with _lock:
        _cache = values
        _cache_time = time.monotonic()
    return dict(values)


def get_value(db: Session, key: str) -> Any:
    return get(db)[key]


def validate_value(key: str, value: Any) -> Any:
    """Return the cleaned value or raise ValueError with a user-readable message."""
    d = DEFINITIONS.get(key)
    if d is None:
        raise ValueError(f"Unknown setting '{key}'.")
    if d.type == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false.")
        return value
    if d.type == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            else:
                raise ValueError(f"{key} must be a whole number.")
    if d.type == "float":
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{key} must be a number.")
        value = float(value)
    if d.type in ("int", "float"):
        if (d.min is not None and value < d.min) or (d.max is not None and value > d.max):
            lo = int(d.min) if d.type == "int" else d.min
            hi = int(d.max) if d.type == "int" else d.max
            raise ValueError(f"{key} must be between {lo} and {hi}.")
        return value
    if d.type == "tools":
        if not isinstance(value, dict):
            raise ValueError("enabled_tools must be an object of language → list of tools.")
        cleaned: dict[str, list[str]] = {}
        for lang, allowed in TOOL_REGISTRY.items():
            tools = value.get(lang, [])
            if not isinstance(tools, list) or not all(isinstance(t, str) for t in tools):
                raise ValueError(f"enabled_tools.{lang} must be a list of tool names.")
            bad = [t for t in tools if t not in allowed]
            if bad:
                raise ValueError(
                    f"enabled_tools.{lang} contains unknown tool(s): {', '.join(bad)}. "
                    f"Allowed: {', '.join(allowed)}."
                )
            cleaned[lang] = [t for t in allowed if t in tools]
        unknown_langs = set(value) - set(TOOL_REGISTRY)
        if unknown_langs:
            raise ValueError(f"enabled_tools has unknown language(s): {', '.join(sorted(unknown_langs))}.")
        return cleaned
    raise ValueError(f"Unsupported setting type for {key}.")


def update(db: Session, changes: dict[str, Any], user_id: int | None) -> dict[str, Any]:
    errors = []
    cleaned = {}
    for key, value in changes.items():
        try:
            cleaned[key] = validate_value(key, value)
        except ValueError as e:
            errors.append({"field": key, "message": str(e)})
    if errors:
        raise AppError(422, "VALIDATION_ERROR", errors[0]["message"], errors)
    for key, value in cleaned.items():
        row = db.get(SystemSetting, key)
        if row is None:
            row = SystemSetting(key=key)
            db.add(row)
        row.value = value
        row.updated_at = utcnow()
        row.updated_by = user_id
    db.commit()
    invalidate_cache()
    return get(db)


def describe(db: Session) -> list[dict[str, Any]]:
    values = get(db)
    return [
        {
            "key": key,
            "value": values[key],
            "default": d.default(),
            "type": d.type,
            "min": d.min,
            "max": d.max,
            "description": d.description,
            "options": TOOL_REGISTRY if d.type == "tools" else None,
        }
        for key, d in DEFINITIONS.items()
    ]
