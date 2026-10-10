"""Severity (8.13), confidence (8.14) and overall levels (8.15)."""

from __future__ import annotations

from app.pipeline import taxonomy
from app.pipeline.types import ReportFinding

SPECIFIC_LINES_MAX_SPAN = 15  # a finding pointing at ≤15 lines counts as "specific lines" (rule 4)


def _tools_text(f: ReportFinding) -> str:
    return ", ".join(f.static_tool_list) if f.static_tool_list else (f.static_tool or "static analysis")


# ---------- 8.13 severity ----------
def severity(f: ReportFinding) -> str:
    if f.category == "security":
        base = taxonomy.base_severity(f.cwe_id)
        if base is None:
            if f.source in ("static", "both"):
                base = f.static_tool_severity or "MEDIUM"
            else:
                base = f.ai_severity or "MEDIUM"
        level = base
        if (
            f.source == "llm"
            and f.ai_severity
            and taxonomy.SEVERITY_RANK[f.ai_severity] > taxonomy.SEVERITY_RANK[base]
            and not f.model_uncertain
        ):
            level = f.ai_severity
        if f.source == "static" and f.ai_assessment == "likely_false_positive":
            level = taxonomy.lower_one(level)
        return level
    # reliability / performance / maintainability
    if f.source == "static":
        level = f.static_tool_severity or "LOW"
    else:
        level = f.ai_severity or f.static_tool_severity or "LOW"
    return taxonomy.cap_severity(level, f.category)


# ---------- 8.14 confidence ----------
def confidence(f: ReportFinding, consistency: str) -> tuple[str, str]:
    """`consistency` is "ran", "disabled" or "failed"."""
    tools = _tools_text(f)
    # 1
    if f.source == "both":
        return (
            "HIGH",
            f"Found by both static analysis ({tools}) and the AI review on the same lines.",
        )
    # 2
    if f.source == "static" and f.ai_assessment == "likely_false_positive":
        return (
            "LOW",
            f"Reported by {tools}, but the AI review judged it a likely false positive.",
        )
    if f.source == "llm":
        # 3
        if f.model_uncertain:
            return (
                "LOW",
                "Reported by the AI only, and the AI said it was uncertain about this issue.",
            )
        if consistency == "disabled":
            return (
                "MEDIUM",
                "Reported by the AI only; the consistency check was not run.",
            )
        if consistency == "failed":
            return (
                "MEDIUM",
                "Reported by the AI only; the consistency check could not run.",
            )
        if not f.consistency_matched:
            return (
                "LOW",
                "Reported by the AI only, and the issue did not appear in the second independent check.",
            )
        specific = (f.end_line - f.start_line + 1) <= SPECIFIC_LINES_MAX_SPAN
        # 4
        if specific and f.cwe_id:
            return (
                "HIGH",
                "Reported consistently in two independent AI reviews, with specific lines and a recognised "
                "weakness category.",
            )
        # 5
        return (
            "MEDIUM",
            (
                "Reported consistently by the AI with specific lines, but not linked to a recognised weakness category."
                if specific
                else "Reported consistently by the AI, but it covers a wide range of lines and needs checking."
            ),
        )
    # 6 (static with assessment agree / not_reviewed)
    verb = "agreed" if f.ai_assessment == "agree" else "did not review it"
    return "MEDIUM", f"Reported by {tools} with a specific rule; the AI review {verb}."


def score(findings: list[ReportFinding], consistency: str) -> list[ReportFinding]:
    for f in findings:
        f.severity = severity(f)
        f.confidence, f.confidence_reason = confidence(f, consistency)
    return findings


# ---------- 8.15 overall levels ----------
def overall_risk(findings: list[ReportFinding]) -> str:
    return taxonomy.max_severity(*(f.severity for f in findings)) or "NONE"


def overall_confidence(findings: list[ReportFinding], ai_available: bool) -> str:
    if not ai_available:
        return "LOW"
    serious = [f.confidence for f in findings if f.severity in ("CRITICAL", "HIGH")]
    if not serious:
        return "MEDIUM"
    return min(serious, key=taxonomy.CONFIDENCE_RANK.__getitem__)
