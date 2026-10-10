"""Check that every ground-truth issue's line range contains its anchor text (Section 17.1).

Usage: python evaluation/scripts/check_ground_truth.py
Exit code 0 when all checks pass.
"""

from __future__ import annotations

import sys

from common import BENCHMARK_DIR, load_ground_truth


def check() -> list[str]:
    problems: list[str] = []
    gt = load_ground_truth()
    if len(gt) != 30:
        problems.append(f"expected 30 samples, found {len(gt)}")
    for sample_id, entry in gt.items():
        path = BENCHMARK_DIR / entry["file"]
        if not path.is_file():
            problems.append(f"{sample_id}: file {entry['file']} not found")
            continue
        lines = path.read_text(encoding="utf-8").rstrip().split("\n")
        if not 15 <= len(lines) <= 60:
            problems.append(f"{sample_id}: {len(lines)} lines (expected 15-60)")
        if entry["clean"] and entry["issues"]:
            problems.append(f"{sample_id}: marked clean but has issues")
        for issue in entry["issues"]:
            start, end = issue["lines"]
            if not 1 <= start <= end <= len(lines):
                problems.append(f"{issue['issue_id']}: line range {start}-{end} outside 1-{len(lines)}")
                continue
            region = "\n".join(lines[start - 1 : end])
            if issue["anchor"] not in region:
                problems.append(f"{issue['issue_id']}: anchor {issue['anchor']!r} not in lines {start}-{end}")
    return problems


def main() -> int:
    problems = check()
    for p in problems:
        print("FAIL:", p)
    if not problems:
        print("Ground truth OK: all anchors found within their line ranges.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
