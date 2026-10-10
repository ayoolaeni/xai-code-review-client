"""Shared helpers for the evaluation scripts (Section 17)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = EVAL_DIR.parent
BENCHMARK_DIR = EVAL_DIR / "benchmark"
RESULTS_DIR = EVAL_DIR / "results"
BACKEND_DIR = REPO_ROOT / "backend"

# Make the backend package importable (the benchmark calls the real pipeline in-process).
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

LANGUAGE_LABELS = {"python": "Python", "javascript": "JavaScript", "java": "Java"}
SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def load_ground_truth() -> dict:
    return json.loads((BENCHMARK_DIR / "ground_truth.json").read_text(encoding="utf-8"))


def read_sample(entry: dict) -> str:
    return (BENCHMARK_DIR / entry["file"]).read_text(encoding="utf-8")


def overlaps(a: tuple[int, int], b: tuple[int, int], tolerance: int = 2) -> bool:
    return a[0] - tolerance <= b[1] and b[0] - tolerance <= a[1]


def cwe_family(cwe: str | None) -> str | None:
    from app.pipeline.taxonomy import cwe_family as _family

    return _family(cwe)


def finding_detects_issue(finding: dict, issue: dict) -> bool:
    """Section 17.3: overlapping lines (±2) and same CWE, or same category when the issue has no CWE."""
    f_lines = (finding["start_line"], finding["end_line"])
    if not overlaps(f_lines, tuple(issue["lines"])):
        return False
    if issue.get("cwe"):
        f_cwe = (
            (finding.get("cwe") or {}).get("id")
            if isinstance(finding.get("cwe"), dict)
            else finding.get("cwe")
        )
        return bool(f_cwe) and cwe_family(f_cwe) == cwe_family(issue["cwe"])
    return finding.get("category") == issue["category"]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
