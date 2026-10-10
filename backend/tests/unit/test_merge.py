"""Merging AI and static findings (Section 8.12, FR11) and consistency matching (8.11)."""

from app.llm.output_schema import (
    Change,
    ExplanationOutput,
    LLMFinding,
    RiskOnlyFinding,
    StaticAssessment,
)
from app.pipeline import merge
from app.pipeline.types import StaticFinding


def sf(
    id,
    tool,
    rule,
    line,
    cwe=None,
    category="security",
    sev="HIGH",
    end=None,
    msg="tool message",
):
    return StaticFinding(id, tool, rule, msg, line, end or line, sev, cwe, None, category)


def af(
    title,
    line,
    cwe=None,
    category="security",
    related=(),
    sev="HIGH",
    uncertain=False,
    end=None,
):
    return LLMFinding(
        title=title,
        category=category,
        start_line=line,
        end_line=end or line,
        description="why",
        evidence="code",
        recommendation="fix",
        severity_suggested=sev,
        cwe_id=cwe,
        model_uncertain=uncertain,
        related_static_ids=list(related),
    )


def explanation(findings, assessments=(), changes=()):
    return ExplanationOutput(
        purpose_summary="Does something useful.",
        breakdown=[{"start_line": 1, "end_line": 30, "title": "All", "explanation": "x"}],
        findings=findings,
        static_assessment=list(assessments),
        improved_code="changed",
        changes=list(changes),
    )


def test_static_grouping_across_tools():
    findings = [
        sf("S1", "bandit", "B608", 6, "CWE-89"),
        sf("S2", "semgrep", "xai-py-sql-string-concat", 7, "CWE-89"),
        sf("S3", "bandit", "B105", 20, "CWE-259"),
        sf("S4", "redactor", "hardcoded-secret", 21, "CWE-798"),
        sf("S5", "eslint", "eqeqeq", 30, None, "reliability"),
    ]
    groups = merge.group_static(findings)
    assert [g.ids for g in groups] == [["S1", "S2"], ["S3", "S4"], ["S5"]]
    assert groups[0].tool_names == "bandit, semgrep"
    assert groups[0].rule_ids == "B608, xai-py-sql-string-concat"


def test_declared_link_gives_both():
    static = [
        sf("S1", "bandit", "B608", 6, "CWE-89"),
        sf("S2", "semgrep", "xai-py-sql", 7, "CWE-89"),
    ]
    exp = explanation(
        [af("SQL injection", 6, "CWE-89", related=["S1"])],
        [StaticAssessment(static_id="S1", verdict="agree", reason="real")],
    )
    findings, _ = merge.merge(static, exp, None)
    assert len(findings) == 1
    f = findings[0]
    assert f.source == "both" and f.static_tool == "bandit, semgrep" and (f.start_line, f.end_line) == (6, 7)
    assert f.ai_assessment == "agree" and f.owasp_category == "A03:2021 – Injection"


def test_positional_link_when_not_declared():
    static = [sf("S1", "bandit", "B605", 10, "CWE-78")]
    findings, _ = merge.merge(static, explanation([af("Command injection", 11, "CWE-78")]), None)
    assert [f.source for f in findings] == ["both"]


def test_positional_link_needs_matching_cwe_or_category():
    static = [sf("S1", "bandit", "B605", 10, "CWE-78")]
    findings, _ = merge.merge(static, explanation([af("Weak hash", 10, "CWE-327")]), None)
    assert sorted(f.source for f in findings) == ["llm", "static"]


def test_far_apart_findings_stay_separate():
    static = [sf("S1", "bandit", "B605", 10, "CWE-78")]
    findings, _ = merge.merge(static, explanation([af("Command injection", 20, "CWE-78")]), None)
    assert sorted(f.source for f in findings) == ["llm", "static"]


def test_static_only_uses_assessment_and_dictionary():
    static = [sf("S1", "bandit", "B324", 4, "CWE-327", msg="Use of weak MD5 hash.")]
    exp = explanation(
        [],
        [
            StaticAssessment(
                static_id="S1",
                verdict="likely_false_positive",
                reason="only a checksum",
            )
        ],
    )
    findings, _ = merge.merge(static, exp, None)
    f = findings[0]
    assert f.source == "static" and f.ai_assessment == "likely_false_positive"
    assert f.title == "Broken or risky crypto algorithm"
    assert "only a checksum" in f.description
    assert f.recommendation.startswith("Use a modern algorithm")


def test_static_only_without_ai_is_not_reviewed():
    findings, _ = merge.merge([sf("S1", "eslint", "no-eval", 3, "CWE-95")], None, None)
    assert findings[0].source == "static" and findings[0].ai_assessment == "not_reviewed"


def test_keys_sorted_by_severity_then_line_and_changes_remapped():
    static = [sf("S1", "bandit", "B608", 9, "CWE-89")]
    exp = explanation(
        [
            af("Bare except", 3, "CWE-396", category="reliability", sev="LOW"),
            af("SQL", 9, "CWE-89", related=["S1"]),
        ],
        changes=[
            Change(
                number=1,
                description="d",
                reason="r",
                related_findings=[2, 1],
                original_lines=[9, 9],
            )
        ],
    )
    findings, changes = merge.merge(static, exp, None)
    for f in findings:
        f.severity = "CRITICAL" if f.cwe_id == "CWE-89" else "LOW"
    findings, changes = merge.assign_keys(findings, changes)
    assert [(f.public_key, f.cwe_id) for f in findings] == [
        ("F1", "CWE-89"),
        ("F2", "CWE-396"),
    ]
    assert changes[0]["related_findings"] == ["F1", "F2"]


def test_consistency_matching():
    a = [
        af("SQL", 10, "CWE-89"),
        af("Hash", 20, "CWE-327"),
        af("Leak", 30, None, "reliability"),
    ]
    b = [
        RiskOnlyFinding(
            title="sqli",
            category="security",
            start_line=11,
            end_line=11,
            severity_suggested="HIGH",
            cwe_id="CWE-89",
        ),
        RiskOnlyFinding(
            title="leak",
            category="reliability",
            start_line=31,
            end_line=31,
            severity_suggested="LOW",
        ),
        RiskOnlyFinding(
            title="other",
            category="performance",
            start_line=50,
            end_line=50,
            severity_suggested="LOW",
        ),
    ]
    c = merge.match_consistency(a, b)
    assert c.matched_indexes == {1, 3}
    assert (c.matched, c.only_in_a, c.only_in_b) == (2, 1, 1)


def test_consistency_prefers_identical_cwe():
    a = [af("A", 10, "CWE-89")]
    b = [
        RiskOnlyFinding(
            title="cat",
            category="security",
            start_line=10,
            end_line=12,
            severity_suggested="HIGH",
        ),
        RiskOnlyFinding(
            title="cwe",
            category="security",
            start_line=11,
            end_line=11,
            severity_suggested="HIGH",
            cwe_id="CWE-89",
        ),
    ]
    c = merge.match_consistency(a, b)
    assert c.matched == 1 and c.only_in_b == 1
