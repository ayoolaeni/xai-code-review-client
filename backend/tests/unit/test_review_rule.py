"""Human-review rule (Section 8.16, FR10)."""

from app.pipeline import review_rule
from app.pipeline.types import ReportFinding


def rf(**kw) -> ReportFinding:
    base = dict(
        category="security",
        title="SQL injection",
        description="d",
        evidence="",
        recommendation="r",
        start_line=6,
        end_line=7,
        source="both",
        severity="LOW",
        confidence="HIGH",
    )
    base.update(kw)
    return ReportFinding(**base)


def test_condition1_critical_or_high_security():
    reasons = review_rule.review_reasons([rf(severity="CRITICAL")], [], True)
    assert reasons == [
        "This code contains a CRITICAL security issue (SQL injection, lines 6–7). A developer with security "
        "experience should confirm the fix before the code is used."
    ]
    assert review_rule.review_reasons([rf(severity="HIGH", category="reliability")], [], True) == []


def test_condition2_uncertain_important_issue():
    reasons = review_rule.review_reasons(
        [rf(category="reliability", severity="MEDIUM", confidence="LOW")], [], True
    )
    assert reasons == [
        "The system is uncertain about a potentially important issue (SQL injection). Please check it yourself."
    ]
    assert (
        review_rule.review_reasons([rf(category="reliability", severity="LOW", confidence="LOW")], [], True)
        == []
    )


def test_condition3_sensitive_domains():
    reasons = review_rule.review_reasons([], ["authentication", "personal_data"], True)
    assert reasons == [
        "This code handles authentication and personal data. Mistakes in these areas have serious consequences, so "
        "a careful human review is advised."
    ]


def test_condition4_fallback():
    reasons = review_rule.review_reasons([], [], False)
    assert reasons == ["The AI explanation could not be produced, so this report is incomplete."]


def test_all_conditions_combined():
    reasons = review_rule.review_reasons(
        [
            rf(severity="CRITICAL"),
            rf(category="reliability", severity="MEDIUM", confidence="LOW"),
        ],
        ["payments"],
        False,
        "The AI service is busy.",
    )
    assert len(reasons) == 4
    assert reasons[-1].endswith("The AI service is busy.")


def test_keyword_domains():
    assert review_rule.detect_domains("def login(user, password): ...") == ["authentication"]
    assert review_rule.detect_domains("import hashlib\nh = hashlib.sha256()") == ["cryptography"]
    assert review_rule.detect_domains("total = amount * rate  # invoice") == ["payments"]
    assert review_rule.detect_domains("send(email, phone)") == ["personal_data"]
    assert review_rule.detect_domains("x = 1 + 2") == []
    # word boundaries: "author" is not "auth", "emails" is not "email"
    assert review_rule.detect_domains("author = 'x'; emails = []") == []


def test_merge_domains_union_in_fixed_order():
    assert review_rule.merge_domains(["payments"], "password = x") == [
        "authentication",
        "payments",
    ]
