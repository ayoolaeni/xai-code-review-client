"""Static-analysis runners: parse stored real outputs, plus live runs when the tools are installed."""

from pathlib import Path

import pytest

from app.static_analysis import bandit_runner, eslint_runner, pmd_runner, semgrep_runner
from app.static_analysis.base import ProcessResult
from app.static_analysis.registry import RUNNERS, run_static_analysis

FIX = Path(__file__).resolve().parents[1] / "fixtures"
OUT = FIX / "tool_outputs"
CODE = FIX / "code"


def _read(name: str) -> str:
    return (OUT / name).read_text(encoding="utf-8-sig")


# ---------- Parsing stored outputs (no tools needed) ----------
def test_parse_bandit_output():
    findings = bandit_runner.parse_output(_read("bandit.json"))
    by_rule = {f.rule_id: f for f in findings}
    assert {"B608", "B605", "B324", "B110"} <= set(by_rule)
    sql = by_rule["B608"]
    assert sql.cwe_id == "CWE-89" and sql.start_line == 9 and sql.category == "security"
    assert sql.owasp_category == "A03:2021 – Injection"
    assert sql.tool == "bandit" and sql.tool_severity == "MEDIUM"


def test_parse_eslint_output():
    findings = eslint_runner.parse_output(_read("eslint.json"))
    rules = {f.rule_id for f in findings}
    assert {"no-eval", "security/detect-child-process", "eqeqeq"} <= rules
    eq = next(f for f in findings if f.rule_id == "eqeqeq")
    assert eq.category == "reliability" and eq.cwe_id is None
    ev = next(f for f in findings if f.rule_id == "no-eval")
    assert ev.cwe_id == "CWE-95" and ev.category == "security" and ev.tool_severity == "2"


def test_parse_eslint_fatal_parse_error():
    data = '[{"messages": [{"ruleId": null, "fatal": true, "message": "Parsing error: Unexpected token", "line": 3}]}]'
    with pytest.raises(eslint_runner.ESLintParseError):
        eslint_runner.parse_output(data)


def test_parse_semgrep_output():
    findings = semgrep_runner.parse_output(_read("semgrep.json"))
    by_rule = {f.rule_id: f for f in findings}
    sql = by_rule["xai-py-sql-string-concat"]
    assert (
        sql.cwe_id == "CWE-89" and sql.category == "security" and sql.owasp_category == "A03:2021 – Injection"
    )
    registry = next(f for f in findings if f.rule_id.startswith("python.lang"))
    assert registry.cwe_id == "CWE-78" and registry.owasp_category == "A03:2021 – Injection"
    bare = by_rule["xai-py-bare-except"]
    assert bare.category == "reliability" and bare.start_line == 23 and bare.end_line == 26
    mutable = by_rule["xai-py-mutable-default"]
    assert mutable.cwe_id is None and mutable.category == "reliability"


def test_parse_pmd_output():
    path = OUT / "pmd.json"
    if not path.exists():
        pytest.skip("PMD fixture not captured")
    findings = pmd_runner.parse_output(_read("pmd.json"))
    rules = {f.rule_id for f in findings}
    assert "EmptyCatchBlock" in rules
    empty = next(f for f in findings if f.rule_id == "EmptyCatchBlock")
    assert empty.cwe_id == "CWE-390" and empty.category == "reliability"


def test_parse_pmd_processing_error():
    data = '{"files": [], "processingErrors": [{"filename": "X.java", "message": "ParseException: bad"}]}'
    with pytest.raises(pmd_runner.PMDProcessingError):
        pmd_runner.parse_output(data)


@pytest.mark.parametrize("rule_file", sorted(semgrep_runner.RULE_FILES.values()))
def test_vendored_semgrep_rules_are_valid_yaml(rule_file):
    """One invalid rule file makes Semgrep reject the whole configuration (found in the Docker run)."""
    import yaml

    data = yaml.safe_load((semgrep_runner.RULES_DIR / rule_file).read_text(encoding="utf-8"))
    assert data["rules"] and all(r["id"].startswith("xai-") for r in data["rules"])


def test_semgrep_engine_error_reported_as_failed(monkeypatch, tmp_path):
    """Exit code 2 with a JSON error (e.g. engine killed) must not look like a clean scan."""
    stdout = '{"results": [], "errors": [{"message": "Error while running rules: engine was killed"}]}'
    monkeypatch.setattr(semgrep_runner.SemgrepRunner, "available", lambda self: True)
    monkeypatch.setattr(semgrep_runner, "_semgrep_version", lambda: "1.0")
    monkeypatch.setattr(semgrep_runner, "run_tool", lambda *a, **k: ProcessResult(2, stdout, ""))
    findings, run = semgrep_runner.SemgrepRunner().run(tmp_path, "x.py", "python")
    assert findings == [] and run.status == "failed" and "engine was killed" in run.message


def test_unavailable_tool_reported_not_raised(monkeypatch):
    monkeypatch.setattr(RUNNERS["semgrep"], "available", lambda: False)
    monkeypatch.setattr(RUNNERS["bandit"], "available", lambda: False)
    result = run_static_analysis("x = 1", "python", ["semgrep", "bandit"])
    statuses = {r.tool: r.status for r in result.tool_runs}
    assert statuses == {"semgrep": "unavailable", "bandit": "unavailable"}
    assert result.findings == []


def test_disabled_tool_marked_skipped(monkeypatch):
    monkeypatch.setattr(RUNNERS["semgrep"], "available", lambda: False)
    result = run_static_analysis("x = 1", "python", ["semgrep"])
    assert {r.tool: r.status for r in result.tool_runs}["bandit"] == "skipped"


def test_redactor_findings_added_and_ids_sorted(monkeypatch):
    from app.pipeline.redaction import redact, synthetic_findings

    for name in RUNNERS:
        monkeypatch.setattr(RUNNERS[name], "available", lambda: False)
    code = 'x = 1\npassword = "hunter2hunter2"\n'
    result = run_static_analysis(code, "python", [], synthetic_findings(redact(code)))
    assert [(f.id, f.tool, f.start_line) for f in result.findings] == [("S1", "redactor", 2)]


# ---------- Live runs (only when the tool is installed) ----------
@pytest.mark.tools
@pytest.mark.skipif(not RUNNERS["bandit"].available(), reason="Bandit not installed")
def test_live_bandit():
    code = (CODE / "vulnerable.py").read_text(encoding="utf-8")
    result = run_static_analysis(code, "python", ["bandit"])
    run = next(r for r in result.tool_runs if r.tool == "bandit")
    assert run.status == "ok" and run.version
    assert any(f.cwe_id == "CWE-89" for f in result.findings)


@pytest.mark.tools
@pytest.mark.skipif(not RUNNERS["eslint"].available(), reason="ESLint not installed")
def test_live_eslint():
    code = (CODE / "vulnerable.js").read_text(encoding="utf-8")
    result = run_static_analysis(code, "javascript", ["eslint"])
    run = next(r for r in result.tool_runs if r.tool == "eslint")
    assert run.status == "ok", run.message
    assert any(f.rule_id == "no-eval" for f in result.findings)


@pytest.mark.tools
@pytest.mark.skipif(not RUNNERS["eslint"].available(), reason="ESLint not installed")
def test_live_eslint_parse_error():
    result = run_static_analysis("function (( {", "javascript", ["eslint"])
    run = next(r for r in result.tool_runs if r.tool == "eslint")
    assert run.status == "failed" and run.message.startswith("ESLint could not parse the code")


@pytest.mark.tools
@pytest.mark.skipif(not RUNNERS["pmd"].available(), reason="PMD not installed")
def test_live_pmd():
    code = (CODE / "Vulnerable.java").read_text(encoding="utf-8")
    result = run_static_analysis(code, "java", ["pmd"])
    run = next(r for r in result.tool_runs if r.tool == "pmd")
    assert run.status == "ok", run.message
    assert any(f.rule_id == "EmptyCatchBlock" for f in result.findings)


@pytest.mark.tools
@pytest.mark.skipif(not RUNNERS["pmd"].available(), reason="PMD not installed")
def test_live_pmd_wrapped_snippet_lines_map_back():
    code = "int risky(String s) {\n    try {\n        return Integer.parseInt(s);\n    } catch (Exception e) {\n    }\n    return 0;\n}"
    result = run_static_analysis(code, "java", ["pmd"])
    assert result.wrapped
    empty = [f for f in result.findings if f.rule_id == "EmptyCatchBlock"]
    assert empty and empty[0].start_line == 4


@pytest.mark.tools
@pytest.mark.skipif(not RUNNERS["semgrep"].available(), reason="Semgrep not installed")
def test_live_semgrep_python():
    code = (CODE / "vulnerable.py").read_text(encoding="utf-8")
    result = run_static_analysis(code, "python", ["semgrep"])
    run = next(r for r in result.tool_runs if r.tool == "semgrep")
    assert run.status == "ok", run.message
    rules = {f.rule_id for f in result.findings}
    assert {
        "xai-py-sql-string-concat",
        "xai-py-os-system",
        "xai-py-weak-hash",
        "xai-py-bare-except",
    } <= rules
