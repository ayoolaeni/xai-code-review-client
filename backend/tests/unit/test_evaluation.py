"""Evaluation scripts (Section 17): ground-truth checker, scoring helpers, user-study scorer."""

import importlib
import sys

import pytest

from tests.conftest import REPO_ROOT

SCRIPTS = REPO_ROOT / "evaluation" / "scripts"


@pytest.fixture(scope="module")
def ev():
    sys.path.insert(0, str(SCRIPTS))
    try:
        yield {
            name: importlib.import_module(name)
            for name in (
                "common",
                "check_ground_truth",
                "score_benchmark",
                "score_user_study",
                "export_for_labelling",
            )
        }
    finally:
        sys.path.remove(str(SCRIPTS))


def test_ground_truth_checker_passes(ev):
    assert ev["check_ground_truth"].check() == []


def test_finding_matching_rule(ev):
    issue = {"cwe": "CWE-89", "category": "security", "lines": [20, 21]}
    detects = ev["common"].finding_detects_issue
    assert detects(
        {
            "start_line": 22,
            "end_line": 22,
            "cwe": {"id": "CWE-89"},
            "category": "security",
        },
        issue,
    )
    assert detects(
        {
            "start_line": 23,
            "end_line": 23,
            "cwe": {"id": "CWE-89"},
            "category": "security",
        },
        issue,
    )
    assert not detects(
        {
            "start_line": 24,
            "end_line": 24,
            "cwe": {"id": "CWE-89"},
            "category": "security",
        },
        issue,
    )
    assert not detects(
        {
            "start_line": 20,
            "end_line": 20,
            "cwe": {"id": "CWE-78"},
            "category": "security",
        },
        issue,
    )
    no_cwe = {"cwe": None, "category": "performance", "lines": [5, 9]}
    assert detects({"start_line": 6, "end_line": 6, "cwe": None, "category": "performance"}, no_cwe)


def test_jaccard_kappa(ev):
    sb = ev["score_benchmark"]
    assert sb.jaccard(set(), set()) == 1.0
    assert sb.jaccard({1, 2}, {2, 3}) == pytest.approx(1 / 3)
    assert sb.cohen_kappa(["1", "0", "1", "1"], ["1", "0", "1", "1"]) == 1.0
    assert sb.cohen_kappa(["1", "0"], ["", ""]) is None


def test_split_claims(ev):
    text = "This code does X.\n\nProblems:\n- SQL injection on line 4 because of concatenation.\n- Not closed file handle."
    claims = ev["export_for_labelling"].split_claims(text)
    assert "SQL injection on line 4 because of concatenation." in claims


def test_sus_and_user_study_scorer(ev, tmp_path):
    us = ev["score_user_study"]
    import pandas as pd

    row = pd.Series({f"sus{i}": (5 if i % 2 else 1) for i in range(1, 11)})
    assert us.sus_score(row) == 100.0
    df = us.synthetic(10)
    res = us.analyse(df)
    assert res["participants"] == 10 and res["sus_mean"] is not None
    assert "q_mean" in res["tests"] and res["tests"]["q_mean"]["p"] is not None
    md = us.to_markdown(res)
    assert "Wilcoxon" in md and "System Usability Scale" in md


def test_benchmark_dry_run_two_samples(ev, tmp_path, monkeypatch):
    from app.services import settings_service

    run_benchmark = importlib.import_module("run_benchmark")
    out = tmp_path / "bench"
    monkeypatch.setenv("BENCHMARK_DATABASE_URL", f"sqlite:///{(tmp_path / 'bench.db').as_posix()}")
    settings_service.invalidate_cache()
    assert (
        run_benchmark.main(
            [
                "--conditions",
                "system",
                "baseline",
                "--runs",
                "2",
                "--out",
                str(out),
                "--samples",
                "P01",
                "P10",
            ]
        )
        == 0
    )
    assert (out / "system" / "P01_run2.json").exists() and (out / "baseline" / "P10_run1.txt").exists()
    metrics, per_sample, notes = ev["score_benchmark"].score(out)
    system_detection = metrics[
        (metrics.metric == "detection_rate") & (metrics.condition == "system") & (metrics.scope == "overall")
    ].value.iloc[0]
    assert system_detection == 1.0
    assert notes  # baseline uses the automatic estimate until reviewers label it
    assert ev["export_for_labelling"].main(["--results", str(out)]) == 0
    assert (out / "labelling.csv").exists()
