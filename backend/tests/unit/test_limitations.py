"""Limitations statement (Section 8.18, NFR3)."""

from app.pipeline import limitations
from app.pipeline.types import ToolRun

OK = [ToolRun("bandit", "1.9", "ok", 1, None)]


def ctx(**kw):
    base = dict(
        provider="mock",
        tool_runs=OK,
        redaction_count=0,
        language="python",
        language_source="user",
    )
    base.update(kw)
    return limitations.LimitationContext(**base)


def test_fixed_statements_always_present():
    notes = limitations.build(ctx())
    assert notes == limitations.FIXED


def test_gemini_data_use():
    assert limitations.GEMINI_DATA_USE in limitations.build(ctx(provider="gemini"))


def test_tool_not_ok():
    notes = limitations.build(
        ctx(tool_runs=[ToolRun("pmd", None, "unavailable", 0, "PMD is not installed.")])
    )
    assert "pmd did not run: PMD is not installed." in notes


def test_redactions():
    assert any(
        n.startswith("2 secret value(s) were masked") for n in limitations.build(ctx(redaction_count=2))
    )


def test_auto_detected_and_mismatch():
    notes = limitations.build(
        ctx(
            language_source="auto",
            language="java",
            language_notes=["You selected Python but the file extension suggests Java."],
        )
    )
    assert "The language was detected automatically as Java." in notes
    assert "You selected Python but the file extension suggests Java." in notes


def test_consistency_states():
    disabled = limitations.build(
        ctx(
            consistency={
                "enabled": False,
                "reason": "skipped to save the daily AI quota",
            }
        )
    )
    assert any("was not run (skipped to save the daily AI quota)" in n for n in disabled)
    failed = limitations.build(ctx(consistency={"enabled": True, "run_b_ok": False}))
    assert any("could not be completed" in n for n in failed)
    only_b = limitations.build(ctx(consistency={"enabled": True, "run_b_ok": True, "only_in_b": 3}))
    assert "The second check found 3 possible issue(s) not reported in the main explanation." in only_b


def test_improved_code_problems():
    notes = limitations.build(ctx(improved_check={"syntax_ok": False}))
    assert limitations.IMPROVED_WARNING in notes
    notes = limitations.build(ctx(improved_check={"syntax_ok": True, "new_high_or_critical": 1}))
    assert limitations.IMPROVED_WARNING in notes


def test_java_wrapped_and_fallback_and_ai_notes_deduplicated():
    notes = limitations.build(
        ctx(
            java_wrapped=True,
            fallback_message="The AI service is busy.",
            ai_limitations=[
                "How f is called is unknown.",
                "How f is called is unknown.",
            ],
        )
    )
    assert limitations.JAVA_WRAPPED in notes
    assert "The AI service is busy." in notes
    assert notes.count("AI note: How f is called is unknown.") == 1
