"""Score the user study (Section 17.6).

    python evaluation/scripts/score_user_study.py --responses evaluation/user_study/responses.csv \
        --out evaluation/results/user_study

    # Try it with synthetic data:
    python evaluation/scripts/score_user_study.py --synthetic 20 --out evaluation/results/user_study_demo

Computes the SUS score per participant (system condition), the explanation-satisfaction questionnaire per
condition and per item, and task performance per condition, with Wilcoxon signed-rank tests (paired by
participant, alpha = .05) and effect size r = Z / sqrt(N). Writes user_study_results.md.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

import pandas as pd
from scipy import stats

from common import load_ground_truth

ALPHA = 0.05
SUS_BENCHMARK = 68.0
Q_ITEMS = [f"q{i}" for i in range(1, 11)]
SUS_ITEMS = [f"sus{i}" for i in range(1, 11)]
COLUMNS = (
    [
        "participant_id",
        "group",
        "condition",
        "sample_id",
        "task_time_s",
        "comprehension_score",
        "risks_found",
        "risks_correct",
        "safety_decision_correct",
    ]
    + Q_ITEMS
    + SUS_ITEMS
    + ["comments"]
)
Q_TEXT = {
    "q1": "I understand what this code does.",
    "q2": "The explanation of the problems is clear.",
    "q3": "The explanation has enough detail.",
    "q4": "The explanation does not include unnecessary detail.",
    "q5": "It helped me decide whether the code is safe to use.",
    "q6": "I understand why the suggested changes are better.",
    "q7": "I could tell how confident the tool was.",
    "q8": "I know when to check the code myself.",
    "q9": "I trust the explanation as much as it deserves.",
    "q10": "The explanation would help me in my own work.",
}


def sus_score(row: pd.Series) -> float:
    """Standard SUS: odd items (x − 1), even items (5 − x); sum × 2.5 → 0–100."""
    total = 0.0
    for i in range(1, 11):
        x = float(row[f"sus{i}"])
        total += (x - 1) if i % 2 == 1 else (5 - x)
    return total * 2.5


def wilcoxon_paired(a: list[float], b: list[float]) -> dict:
    """Wilcoxon signed-rank test with W, p, Z (normal approximation) and r = Z/sqrt(N)."""
    pairs = [(x, y) for x, y in zip(a, b, strict=False) if not (math.isnan(x) or math.isnan(y))]
    diffs = [x - y for x, y in pairs]
    nonzero = [d for d in diffs if d != 0]
    n = len(nonzero)
    if n == 0:
        return {"n": len(pairs), "W": None, "p": None, "Z": None, "r": None}
    res = stats.wilcoxon([x for x, _ in pairs], [y for _, y in pairs], zero_method="wilcox")
    w = float(res.statistic)
    mean_w = n * (n + 1) / 4
    sd_w = math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    z = (w - mean_w) / sd_w if sd_w else 0.0
    return {
        "n": len(pairs),
        "W": w,
        "p": float(res.pvalue),
        "Z": z,
        "r": abs(z) / math.sqrt(len(pairs)),
    }


def seeded_counts() -> dict[str, int]:
    gt = load_ground_truth()
    return {sid: sum(1 for i in e["issues"] if i["seeded"]) for sid, e in gt.items()}


def analyse(df: pd.DataFrame) -> dict:
    df = df.copy()
    for c in (
        Q_ITEMS
        + SUS_ITEMS
        + [
            "task_time_s",
            "comprehension_score",
            "risks_found",
            "risks_correct",
            "safety_decision_correct",
        ]
    ):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    seeded = seeded_counts()
    df["risk_accuracy"] = [
        ((r.risks_correct / seeded.get(r.sample_id, 1)) if seeded.get(r.sample_id) else float("nan"))
        for r in df.itertuples()
    ]
    df["q_mean"] = df[Q_ITEMS].mean(axis=1)

    # SUS: system condition only, one score per participant.
    sus_rows = df[(df.condition == "system")].dropna(subset=SUS_ITEMS).drop_duplicates("participant_id")
    sus = sus_rows.apply(sus_score, axis=1) if not sus_rows.empty else pd.Series(dtype=float)
    sus_test = None
    if len(sus) >= 2:
        t = stats.ttest_1samp(sus, SUS_BENCHMARK)
        sus_test = {"t": float(t.statistic), "p": float(t.pvalue)}

    # Per participant and condition (mean over that condition's samples) → paired tests.
    per = df.groupby(["participant_id", "condition"]).mean(numeric_only=True).reset_index()
    wide = per.pivot(index="participant_id", columns="condition")
    tests = {}
    for measure in [
        "q_mean",
        *Q_ITEMS,
        "comprehension_score",
        "risk_accuracy",
        "safety_decision_correct",
        "task_time_s",
    ]:
        if ("system" in wide[measure]) and ("baseline" in wide[measure]):
            tests[measure] = {
                "system_mean": float(wide[measure]["system"].mean()),
                "baseline_mean": float(wide[measure]["baseline"].mean()),
                **wilcoxon_paired(list(wide[measure]["system"]), list(wide[measure]["baseline"])),
            }
    return {
        "participants": int(df.participant_id.nunique()),
        "sus_scores": sus.tolist(),
        "sus_mean": float(sus.mean()) if len(sus) else None,
        "sus_sd": float(sus.std(ddof=1)) if len(sus) > 1 else None,
        "sus_test": sus_test,
        "tests": tests,
    }


def _fmt(v, digits=2) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:.{digits}f}"


def to_markdown(res: dict) -> str:
    lines = ["# User study results", "", f"Participants: **{res['participants']}**", ""]
    lines += ["## System Usability Scale (system condition)", ""]
    if res["sus_mean"] is not None:
        lines.append(
            f"Mean SUS = **{_fmt(res['sus_mean'], 1)}** (SD {_fmt(res['sus_sd'], 1)}); benchmark = {SUS_BENCHMARK:.0f}."
        )
        if res["sus_test"]:
            verdict = "above" if res["sus_mean"] > SUS_BENCHMARK else "below"
            sig = "significantly " if res["sus_test"]["p"] < ALPHA else "not significantly "
            lines.append(
                f"One-sample t-test against 68: t = {_fmt(res['sus_test']['t'])}, p = {_fmt(res['sus_test']['p'], 3)} "
                f"— the mean is {sig}{verdict} the benchmark."
            )
    lines += [
        "",
        "## Explanation questionnaire and task performance (paired Wilcoxon signed-rank, α = .05)",
        "",
        "| Measure | System mean | Baseline mean | N | W | p | Z | r | Significant |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    names = {
        "q_mean": "Questionnaire overall (q1–q10)",
        "comprehension_score": "Comprehension (0–2)",
        "risk_accuracy": "Risk identification accuracy",
        "safety_decision_correct": "Safety decision correct",
        "task_time_s": "Task time (s)",
        **{k: f"{k}: {v}" for k, v in Q_TEXT.items()},
    }
    for measure, t in res["tests"].items():
        sig = "yes" if t["p"] is not None and t["p"] < ALPHA else "no"
        lines.append(
            f"| {names.get(measure, measure)} | {_fmt(t['system_mean'])} | {_fmt(t['baseline_mean'])} | "
            f"{t['n']} | {_fmt(t['W'], 1)} | {_fmt(t['p'], 3)} | {_fmt(t['Z'])} | {_fmt(t['r'])} | {sig} |"
        )
    lines += ["", "Effect size r: 0.1 small, 0.3 medium, 0.5 large."]
    return "\n".join(lines) + "\n"


def synthetic(n: int, seed: int = 7) -> pd.DataFrame:
    """Synthetic responses with the template's columns (for trying the scorer)."""
    rng = random.Random(seed)
    rows = []
    pairs = {
        "A": [
            ("system", "P01"),
            ("baseline", "J04"),
            ("system", "V05"),
            ("baseline", "P05"),
        ],
        "B": [
            ("baseline", "P01"),
            ("system", "J04"),
            ("baseline", "V05"),
            ("system", "P05"),
        ],
    }
    for p in range(1, n + 1):
        group = "A" if p % 2 else "B"
        sus = [rng.choice([4, 5]) if i % 2 == 1 else rng.choice([1, 2]) for i in range(1, 11)]
        for condition, sample in pairs[group]:
            good = condition == "system"
            rows.append(
                {
                    "participant_id": f"P{p:02d}",
                    "group": group,
                    "condition": condition,
                    "sample_id": sample,
                    "task_time_s": rng.randint(150, 300) - (30 if good else 0),
                    "comprehension_score": (rng.choice([1, 2, 2]) if good else rng.choice([0, 1, 2])),
                    "risks_found": rng.randint(1, 3),
                    "risks_correct": 1 if good or rng.random() < 0.5 else 0,
                    "safety_decision_correct": 1 if good or rng.random() < 0.6 else 0,
                    **{q: min(5, max(1, rng.randint(3, 5) if good else rng.randint(2, 4))) for q in Q_ITEMS},
                    **(
                        {f"sus{i}": sus[i - 1] for i in range(1, 11)}
                        if good
                        else dict.fromkeys(SUS_ITEMS, "")
                    ),
                    "comments": "",
                }
            )
    return pd.DataFrame(rows, columns=COLUMNS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--responses", type=Path)
    parser.add_argument("--synthetic", type=int, help="generate N synthetic participants instead")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.synthetic:
        df = synthetic(args.synthetic)
        args.out.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.out / "synthetic_responses.csv", index=False)
    elif args.responses:
        df = pd.read_csv(args.responses)
    else:
        parser.error("give --responses or --synthetic")
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        print(f"Missing columns: {missing}", file=sys.stderr)
        return 1
    res = analyse(df)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "user_study_results.md").write_text(to_markdown(res), encoding="utf-8")
    print(to_markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
