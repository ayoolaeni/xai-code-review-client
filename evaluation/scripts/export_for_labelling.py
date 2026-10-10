"""Create the reviewer labelling sheet for both conditions (Section 17.3).

    python evaluation/scripts/export_for_labelling.py --results evaluation/results/<timestamp>

Writes <results>/labelling.csv. Two reviewers fill the reviewer1_* and reviewer2_* columns independently:
  * ground_truth_issue rows: detected (0/1) — did the output identify this seeded issue?
  * claim rows:              valid_claim (0/1) — is this reported problem real?
  * explanation rows:        correct_explanation (0 = wrong, 1 = partly correct, 2 = correct)
score_benchmark.py reads the sheet back (and computes Cohen's kappa between the reviewers).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from common import load_ground_truth

COLUMNS = [
    "condition",
    "sample_id",
    "run",
    "item_type",
    "item_id",
    "text",
    "reviewer1_detected",
    "reviewer2_detected",
    "reviewer1_valid_claim",
    "reviewer2_valid_claim",
    "reviewer1_correct_explanation",
    "reviewer2_correct_explanation",
]

_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def split_claims(text: str) -> list[str]:
    """Split free text into claimed problems: bullet/numbered items, otherwise paragraphs."""
    lines = text.splitlines()
    items: list[str] = []
    current: list[str] = []
    for line in lines:
        if _BULLET.match(line):
            if current:
                items.append(" ".join(current).strip())
            current = [_BULLET.sub("", line).strip()]
        elif not line.strip():
            if current:
                items.append(" ".join(current).strip())
                current = []
        else:
            current.append(line.strip())
    if current:
        items.append(" ".join(current).strip())
    # Keep paragraphs that look like problem statements; headings alone are dropped.
    return [i for i in items if len(i) > 15]


def rows_for_results(results: Path) -> list[dict]:
    gt = load_ground_truth()
    rows: list[dict] = []
    for path in sorted((results / "system").glob("*_run*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        sid, run, report = data["sample_id"], data["run"], data["report"]
        for issue in gt[sid]["issues"]:
            rows.append(
                _row(
                    "system",
                    sid,
                    run,
                    "ground_truth_issue",
                    issue["issue_id"],
                    issue["description"],
                )
            )
        for f in report["findings"]:
            cwe = (f.get("cwe") or {}).get("id") or "no CWE"
            text = f"{f['title']} (lines {f['start_line']}-{f['end_line']}, {cwe}, {f['severity']}): {f['description']}"
            rows.append(_row("system", sid, run, "claim", f["key"], text))
        rows.append(
            _row(
                "system",
                sid,
                run,
                "explanation",
                "purpose",
                report["overview"]["purpose_summary"],
            )
        )
        breakdown = " | ".join(
            f"{s['start_line']}-{s['end_line']} {s['title']}: {s['explanation']}" for s in report["breakdown"]
        )
        if breakdown:
            rows.append(_row("system", sid, run, "explanation", "breakdown", breakdown))
        changes = " | ".join(
            f"{c['number']}. {c['description']} — {c['reason']}" for c in report["improved"]["changes"]
        )
        if changes:
            rows.append(_row("system", sid, run, "explanation", "change_reasons", changes))
    for path in sorted((results / "baseline").glob("*_run*.txt")):
        sid, run = path.stem.split("_run")
        text = path.read_text(encoding="utf-8")
        for issue in gt[sid]["issues"]:
            rows.append(
                _row(
                    "baseline",
                    sid,
                    int(run),
                    "ground_truth_issue",
                    issue["issue_id"],
                    issue["description"],
                )
            )
        for i, claim in enumerate(split_claims(text), start=1):
            rows.append(_row("baseline", sid, int(run), "claim", f"C{i}", claim))
        rows.append(_row("baseline", sid, int(run), "explanation", "full_text", text))
    return rows


def _row(condition, sid, run, item_type, item_id, text) -> dict:
    row = dict.fromkeys(COLUMNS, "")
    row.update(
        condition=condition,
        sample_id=sid,
        run=run,
        item_type=item_type,
        item_id=item_id,
        text=" ".join(str(text).split()),
    )
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = rows_for_results(args.results)
    out = args.results / "labelling.csv"
    if out.exists():
        print(f"{out} already exists — not overwriting reviewers' work. Delete it first to regenerate.")
        return 1
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
