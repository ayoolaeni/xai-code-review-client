"""Severity (8.13), confidence — one test per row of 8.14 — and overall levels (8.15)."""

from app.pipeline import scoring
from app.pipeline.types import ReportFinding


def rf(**kw) -> ReportFinding:
    base = dict(
        category="security",
        title="t",
        description="d",
        evidence="",
        recommendation="r",
        start_line=5,
        end_line=5,
        source="llm",
    )
    base.update(kw)
    return ReportFinding(**base)


# ---------- severity ----------
def test_security_severity_from_cwe_table():
    assert scoring.severity(rf(cwe_id="CWE-89", source="both", static_tool_severity="MEDIUM")) == "CRITICAL"


def test_security_without_cwe_uses_tool_level_or_ai():
    assert scoring.severity(rf(source="static", static_tool_severity="LOW")) == "LOW"
    assert scoring.severity(rf(source="llm", ai_severity="HIGH")) == "HIGH"


def test_llm_may_raise_severity_only_when_certain():
    assert scoring.severity(rf(cwe_id="CWE-327", ai_severity="CRITICAL")) == "CRITICAL"
    assert scoring.severity(rf(cwe_id="CWE-327", ai_severity="CRITICAL", model_uncertain=True)) == "MEDIUM"


def test_static_false_positive_lowered_one_level():
    f = rf(cwe_id="CWE-89", source="static", ai_assessment="likely_false_positive")
    assert scoring.severity(f) == "HIGH"
    assert (
        scoring.severity(rf(cwe_id="CWE-209", source="static", ai_assessment="likely_false_positive"))
        == "LOW"
    )


def test_category_caps():
    assert scoring.severity(rf(category="reliability", ai_severity="CRITICAL")) == "HIGH"
    assert scoring.severity(rf(category="performance", ai_severity="HIGH")) == "MEDIUM"
    assert scoring.severity(rf(category="maintainability", ai_severity="CRITICAL")) == "MEDIUM"
    assert (
        scoring.severity(rf(category="maintainability", source="static", static_tool_severity=None)) == "LOW"
    )


# ---------- confidence: one test per rule ----------
def test_rule1_both_is_high():
    c, reason = scoring.confidence(rf(source="both", static_tool_list=["bandit", "semgrep"]), "ran")
    assert (
        c == "HIGH"
        and reason == "Found by both static analysis (bandit, semgrep) and the AI review on the same lines."
    )


def test_rule2_static_false_positive_is_low():
    c, reason = scoring.confidence(
        rf(
            source="static",
            static_tool_list=["bandit"],
            ai_assessment="likely_false_positive",
        ),
        "ran",
    )
    assert c == "LOW" and "likely false positive" in reason


def test_rule3_llm_uncertain_is_low():
    c, reason = scoring.confidence(rf(model_uncertain=True, consistency_matched=True, cwe_id="CWE-89"), "ran")
    assert c == "LOW" and "uncertain" in reason


def test_rule3_llm_not_matched_is_low():
    c, reason = scoring.confidence(rf(consistency_matched=False, cwe_id="CWE-89"), "ran")
    assert c == "LOW" and "second independent check" in reason


def test_rule4_llm_matched_specific_with_cwe_is_high():
    c, reason = scoring.confidence(rf(consistency_matched=True, cwe_id="CWE-89"), "ran")
    assert c == "HIGH" and "two independent AI reviews" in reason


def test_rule5_llm_matched_without_cwe_is_medium():
    c, reason = scoring.confidence(rf(consistency_matched=True, cwe_id=None, category="performance"), "ran")
    assert c == "MEDIUM" and "not linked to a recognised weakness category" in reason


def test_rule6_static_agree_or_not_reviewed_is_medium():
    c, reason = scoring.confidence(
        rf(source="static", static_tool_list=["pmd"], ai_assessment="agree"), "ran"
    )
    assert c == "MEDIUM" and reason == "Reported by pmd with a specific rule; the AI review agreed."
    c, reason = scoring.confidence(
        rf(source="static", static_tool_list=["pmd"], ai_assessment="not_reviewed"),
        "ran",
    )
    assert c == "MEDIUM" and reason.endswith("did not review it.")


def test_consistency_disabled_or_failed_gives_medium():
    c, reason = scoring.confidence(rf(consistency_matched=None, cwe_id="CWE-89"), "disabled")
    assert c == "MEDIUM" and reason == "Reported by the AI only; the consistency check was not run."
    c, reason = scoring.confidence(rf(consistency_matched=None, cwe_id="CWE-89"), "failed")
    assert c == "MEDIUM" and "could not run" in reason
    # model_uncertain still gives LOW (rule 3 still applies to uncertainty)
    assert scoring.confidence(rf(model_uncertain=True), "disabled")[0] == "LOW"


# ---------- overall ----------
def test_overall_risk():
    assert scoring.overall_risk([]) == "NONE"
    assert scoring.overall_risk([rf(severity="LOW"), rf(severity="HIGH")]) == "HIGH"


def test_overall_confidence():
    findings = [
        rf(severity="CRITICAL", confidence="HIGH"),
        rf(severity="HIGH", confidence="MEDIUM"),
        rf(severity="LOW", confidence="LOW"),
    ]
    assert scoring.overall_confidence(findings, True) == "MEDIUM"
    assert scoring.overall_confidence([rf(severity="LOW", confidence="LOW")], True) == "MEDIUM"
    assert scoring.overall_confidence(findings, False) == "LOW"
