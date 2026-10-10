"""Versioned prompt templates (Section 8.7, NFR9). Never edit a released version; add v2 instead."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

PROMPTS_DIR = Path(__file__).parent
NAMES = ("system", "explain_user", "risks_only_user", "repair_user", "baseline_user")


class _StrictDict(dict):
    """format_map dictionary that raises on missing keys (no silent empty placeholders)."""

    def __missing__(self, key):
        raise KeyError(f"Prompt placeholder '{{{key}}}' has no value")


@lru_cache
def load(version: str, name: str) -> str:
    if name not in NAMES:
        raise ValueError(f"Unknown prompt '{name}'")
    path = PROMPTS_DIR / version / f"{name}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt '{name}' not found for version '{version}'")
    return path.read_text(encoding="utf-8").rstrip("\n")


def render(version: str, name: str, **values: object) -> str:
    return load(version, name).format_map(_StrictDict({k: str(v) for k, v in values.items()}))


def json_schema_text(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema(), indent=2)
