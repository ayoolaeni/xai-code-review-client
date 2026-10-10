"""Score the benchmark (Section 17.4).

    python evaluation/scripts/score_benchmark.py --results evaluation/results/<timestamp>

System metrics are computed from the report JSON. Baseline detection, precision and explanation correctness
come from the reviewers' labelling.csv (export_for_labelling.py). Until that sheet is filled, the baseline is
scored with an automatic keyword estimate that is clearly marked as such in the output.

Writes metrics.csv, metrics.md (tables for Chapter Four) and per_sample.csv into the results folder.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

from common import (
    LANGUAGE_LABELS,
    SEVERITY_RANK,
    finding_detects_issue,
    load_ground_truth,
)
from export_for_labelling import split_claims

CLEAN = ("P10", "J10", "V10")

# Keywords for the automatic baseline estimate (used only until reviewers label the baseline).
KEYWORDS = {
    "CWE-89": r"sql injection|parameteri[sz]ed|prepared statement",
    "CWE-78": r"command injection|shell injection|os\.system|child_process|runtime\.exec|shell=",
    "CWE-798": r"hard[- ]?coded|secret|credential|password in (the )?(source|code)|api key",
    "CWE-502": r"deseriali[sz]|pickle|objectinputstream",
    "CWE-22": r"path traversal|directory traversal|\.\./",
    "CWE-327": r"md5|sha-?1|weak hash|insecure hash|bcrypt|argon2",
    "CWE-95": r"\beval\b|code injection",
    "CWE-404": r"not closed|never closed|close the (file|stream|reader)|resource leak|with statement|try-with-resources",
    "CWE-390": r"bare except|swallow|ignor\w+ (the )?(error|exception)|empty catch|except: ?pass",
    "CWE-79": r"\bxss\b|cross[- ]site scripting|innerhtml",
    "CWE-338": r"math\.random|predictable|cryptographically",
    "CWE-1321": r"prototype pollution|__proto__",
    "CWE-703": r"error handling|response\.ok|unhandled|reject",
    "CWE-611": r"\bxxe\b|external entit",
    "CWE-476": r"null pointer|nullpointer|null check|may be null|returns null",
    "performance": r"o\(n\^?2\)|quadratic|inefficient|performance|stringbuilder|slow",
    "reliability": r"mutable default|default argument",
    "maintainability": r"===|strict equality|loose equality",
}


# ---------- helpers ----------
def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def signature(findings: list[dict]) -> set:
    """(CWE or category, 5-line bucket) for the consistency metric."""
    out = set()
    for f in findings:
        key = (f.get("cwe") or {}).get("id") or f["category"]
        out.add((key, (f["start_line"] - 1) // 5))
    return out


def cohen_kappa(a: list, b: list) -> float | None:
    pairs = [(x, y) for x, y in zip(a, b, strict=False) if x != "" and y != ""]
    if not pairs:
        return None
    labels = sorted({p for pair in pairs for p in pair})
    n = len(pairs)
    po = sum(1 for x, y in pairs if x == y) / n
    pe = sum(
        (sum(1 for x, _ in pairs if x == lab) / n) * (sum(1 for _, y in pairs if y == lab) / n)
        for lab in labels
    )
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def _num(v: str) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_labels(results: Path) -> pd.DataFrame | None:
    path = results / "labelling.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, dtype=str).fillna("")
    filled = df[[c for c in df.columns if c.startswith("reviewer")]].replace("", pd.NA).notna().any().any()
    return df if filled else None


def _consensus(row: pd.Series, field: str) -> float | None:
    vals = [_num(row.get(f"reviewer{i}_{field}", "")) for i in (1, 2)]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


# ---------- scoring ----------
def score(results: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    gt = load_ground_truth()
    labels = load_labels(results)
    notes: list[str] = []
    per_sample: list[dict] = []
    system_reports: dict[tuple[str, int], dict] = {}
    for path in sorted((results / "system").glob("*_run*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        system_reports[(data["sample_id"], data["run"])] = data["report"]
    baseline_texts: dict[tuple[str, int], str] = {}
    for path in sorted((results / "baseline").glob("*_run*.txt")):
        sid, run = path.stem.split("_run")
        baseline_texts[(sid, int(run))] = path.read_text(encoding="utf-8")

    # --- system ---
    for (sid, run), report in system_reports.items():
        entry = gt[sid]
        seeded = [i for i in entry["issues"] if i["seeded"]]
        detected = [i for i in seeded if any(finding_detects_issue(f, i) for f in report["findings"])]
        matched_any = [
            f for f in report["findings"] if any(finding_detects_issue(f, i) for i in entry["issues"])
        ]
        false_alarms = (
            sum(1 for f in report["findings"] if SEVERITY_RANK[f["severity"]] >= 1) if sid in CLEAN else 0
        )
        complete = int(
            all(f.get("severity") and f.get("confidence") for f in report["findings"])
            and bool(report["transparency"]["limitations"])
            and report["overview"]["human_review_advised"] is not None
        )
        per_sample.append(
            {
                "condition": "system",
                "sample_id": sid,
                "run": run,
                "language": entry["language"],
                "seeded": len(seeded),
                "detected": len(detected),
                "findings": len(report["findings"]),
                "auto_valid_findings": len(matched_any),
                "false_alarms_clean": false_alarms,
                "transparency_complete": complete,
                "ai_available": int(report["overview"]["ai_explanation_available"]),
            }
        )

    # --- baseline ---
    baseline_auto = labels is None or not (labels["condition"] == "baseline").any()
    if baseline_texts and baseline_auto:
        notes.append(
            "Baseline detection and precision use an AUTOMATIC KEYWORD ESTIMATE because the reviewers' "
            "labelling.csv is missing or empty. Replace it with reviewer labels for the final results."
        )
    for (sid, run), text in baseline_texts.items():
        entry = gt[sid]
        seeded = [i for i in entry["issues"] if i["seeded"]]
        if not baseline_auto:
            rows = labels[
                (labels.condition == "baseline") & (labels.sample_id == sid) & (labels.run == str(run))
            ]
            gt_rows = rows[rows.item_type == "ground_truth_issue"]
            seeded_ids = {i["issue_id"] for i in seeded}
            detected = sum(
                1
                for _, r in gt_rows.iterrows()
                if r.item_id in seeded_ids and (_consensus(r, "detected") or 0) >= 0.5
            )
            claims = rows[rows.item_type == "claim"]
            valid = sum(1 for _, r in claims.iterrows() if (_consensus(r, "valid_claim") or 0) >= 0.5)
            n_claims = len(claims)
        else:
            low = text.lower()
            detected = sum(
                1 for i in seeded if re.search(KEYWORDS.get(i["cwe"] or i["category"], r"$^"), low)
            )
            n_claims = len(split_claims(text))
            valid = min(detected, n_claims)
        per_sample.append(
            {
                "condition": "baseline",
                "sample_id": sid,
                "run": run,
                "language": entry["language"],
                "seeded": len(seeded),
                "detected": detected,
                "findings": n_claims,
                "auto_valid_findings": valid,
                "false_alarms_clean": None,
                "transparency_complete": 0,
                "ai_available": 1,
            }
        )

    ps = pd.DataFrame(per_sample)
    metrics: list[dict] = []

    def add(metric, condition, scope, value, note=""):
        metrics.append(
            {
                "metric": metric,
                "condition": condition,
                "scope": scope,
                "value": None if value is None else round(float(value), 4),
                "note": note,
            }
        )

    for cond in ("system", "baseline"):
        sub = ps[ps.condition == cond] if not ps.empty else ps
        if sub.empty:
            continue
        add(
            "detection_rate",
            cond,
            "overall",
            sub.detected.sum() / max(1, sub.seeded.sum()),
        )
        for lang in ("python", "javascript", "java"):
            s = sub[sub.language == lang]
            if not s.empty:
                add(
                    "detection_rate",
                    cond,
                    LANGUAGE_LABELS[lang],
                    s.detected.sum() / max(1, s.seeded.sum()),
                )
        # Precision: reviewer labels when available, otherwise findings matching the ground truth.
        precision, note = None, ""
        if labels is not None and (labels.condition == cond).any():
            claims = labels[(labels.condition == cond) & (labels.item_type == "claim")]
            vals = [_consensus(r, "valid_claim") for _, r in claims.iterrows()]
            vals = [v for v in vals if v is not None]
            if vals:
                precision, note = (
                    sum(v >= 0.5 for v in vals) / len(vals),
                    "reviewer labels",
                )
        if precision is None:
            precision = sub.auto_valid_findings.sum() / max(1, sub.findings.sum())
            note = (
                "automatic (findings matching the ground truth)"
                if cond == "system"
                else "automatic keyword estimate"
            )
        add("precision", cond, "overall", precision, note)
        if cond == "system":
            clean = sub[sub.sample_id.isin(CLEAN)]
            add(
                "false_alarms_on_clean_samples",
                cond,
                "P10+J10+V10 (per run)",
                clean.false_alarms_clean.sum() / max(1, clean.run.nunique()),
            )
            add(
                "transparency_completeness",
                cond,
                "overall",
                sub.transparency_complete.mean(),
            )
            add("ai_explanation_available", cond, "overall", sub.ai_available.mean())
        # Consistency between run 1 and run 2.
        if cond == "system":
            sims = []
            for sid in sub.sample_id.unique():
                r1, r2 = system_reports.get((sid, 1)), system_reports.get((sid, 2))
                if r1 and r2:
                    sims.append(jaccard(signature(r1["findings"]), signature(r2["findings"])))
            if sims:
                add(
                    "consistency_jaccard",
                    cond,
                    "mean over samples",
                    sum(sims) / len(sims),
                )
        # Explanation correctness and inter-rater agreement (reviewers).
        if labels is not None and (labels.condition == cond).any():
            expl = labels[(labels.condition == cond) & (labels.item_type == "explanation")]
            scores = [
                v for v in (_consensus(r, "correct_explanation") for _, r in expl.iterrows()) if v is not None
            ]
            if scores:
                add(
                    "explanation_correctness",
                    cond,
                    "mean (0-2)",
                    sum(scores) / len(scores),
                    "reviewer labels",
                )
            rows = labels[labels.condition == cond]
            for field in ("detected", "valid_claim", "correct_explanation"):
                k = cohen_kappa(list(rows[f"reviewer1_{field}"]), list(rows[f"reviewer2_{field}"]))
                if k is not None:
                    add(f"cohens_kappa_{field}", cond, "reviewer 1 vs 2", k)
        if cond == "baseline":
            add(
                "transparency_completeness",
                cond,
                "overall",
                None,
                "rated by reviewers (the baseline has no structured severity/confidence/limitations)",
            )
    return pd.DataFrame(metrics), ps, notes


def to_markdown(metrics: pd.DataFrame, ps: pd.DataFrame, notes: list[str], manifest: dict | None) -> str:
    lines = ["# Benchmark results", ""]
    if manifest:
        lines += [
            f"- Provider / model: **{manifest.get('provider')} / {manifest.get('model')}**",
            f"- Prompt version: {manifest.get('prompt_version')} · runs: {manifest.get('runs')} · "
            f"date: {manifest.get('created_at', '')[:10]} · commit: {(manifest.get('git_commit') or 'n/a')[:10]}",
            "",
        ]
    for n in notes:
        lines += [f"> **Note:** {n}", ""]
    lines += [
        "## Main metrics",
        "",
        "| Metric | Condition | Scope | Value | Note |",
        "|---|---|---|---|---|",
    ]
    for _, r in metrics.iterrows():
        value = (
            "—"
            if pd.isna(r.value)
            else (
                f"{r.value:.1%}"
                if r.metric
                in (
                    "detection_rate",
                    "precision",
                    "transparency_completeness",
                    "ai_explanation_available",
                )
                else f"{r.value:.3f}"
            )
        )
        lines.append(f"| {r.metric.replace('_', ' ')} | {r.condition} | {r.scope} | {value} | {r.note} |")
    lines += [
        "",
        "## Detection per sample (system, all runs)",
        "",
        "| Sample | Language | Seeded | Detected (per run) |",
        "|---|---|---|---|",
    ]
    sys_ps = ps[ps.condition == "system"] if not ps.empty else ps
    grouped: dict[str, list] = defaultdict(list)
    for _, r in sys_ps.sort_values(["sample_id", "run"]).iterrows():
        grouped[r.sample_id].append(r)
    for sid, rows in grouped.items():
        lines.append(
            f"| {sid} | {LANGUAGE_LABELS[rows[0].language]} | {rows[0].seeded} | "
            f"{', '.join(str(int(r.detected)) for r in rows)} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args(argv)
    metrics, ps, notes = score(args.results)
    if metrics.empty:
        print("No results found to score.", file=sys.stderr)
        return 1
    manifest_path = args.results / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    metrics.to_csv(args.results / "metrics.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    ps.to_csv(args.results / "per_sample.csv", index=False)
    (args.results / "metrics.md").write_text(to_markdown(metrics, ps, notes, manifest), encoding="utf-8")
    print((args.results / "metrics.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
