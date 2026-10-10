"""The limitations statement of every report (Section 8.18, NFR3)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.pipeline.language import LABELS
from app.pipeline.types import ToolRun
from app.pipeline.verify_improved import WARNING as IMPROVED_WARNING

FIXED = [
    "The code was analysed as text only. It was never run, so behaviour that depends on runtime data, other files "
    "or external services could not be checked.",
    "AI explanations can be incomplete or wrong, and the AI's stated reasoning may not reflect how it produced its "
    "answer. Treat this report as a starting point for your own review.",
    "Static analysis tools can miss real problems and can report problems that are not real.",
]
GEMINI_DATA_USE = (
    "This system uses the free tier of the Google Gemini API, so the code you submit may be used by Google to "
    "improve its products. Do not submit confidential code."
)
JAVA_WRAPPED = (
    "The Java code had no class around it, so it was wrapped in a class called Snippet for analysis; line numbers "
    "still refer to your original code."
)


@dataclass
class LimitationContext:
    provider: str
    tool_runs: list[ToolRun]
    redaction_count: int
    language: str
    language_source: str
    language_notes: list[str] = field(default_factory=list)
    consistency: dict | None = None
    improved_check: dict | None = None
    java_wrapped: bool = False
    fallback_message: str | None = None
    ai_limitations: list[str] = field(default_factory=list)


def build(ctx: LimitationContext) -> list[str]:
    notes: list[str] = list(FIXED)
    if ctx.provider == "gemini":
        notes.append(GEMINI_DATA_USE)
    if ctx.fallback_message:
        notes.append(ctx.fallback_message)
    for run in ctx.tool_runs:
        if run.status != "ok":
            notes.append(f"{run.tool} did not run: {run.message or run.status}")
    if ctx.redaction_count > 0:
        notes.append(
            f"{ctx.redaction_count} secret value(s) were masked before the code was sent to the AI service, so the "
            "AI saw placeholders instead of the real values."
        )
    if ctx.language_source == "auto":
        notes.append(f"The language was detected automatically as {LABELS[ctx.language]}.")
    notes.extend(ctx.language_notes)
    c = ctx.consistency
    if c is not None and not ctx.fallback_message:
        if not c.get("enabled"):
            why = f" ({c['reason']})" if c.get("reason") else ""
            notes.append(
                f"The second, independent AI check was not run{why}, so AI-only findings were not cross-checked."
            )
        elif c.get("run_b_ok") is False:
            notes.append(
                "The second, independent AI check could not be completed, so AI-only findings were not cross-checked."
            )
        elif c.get("only_in_b", 0) > 0:
            notes.append(
                f"The second check found {c['only_in_b']} possible issue(s) not reported in the main explanation."
            )
    check = ctx.improved_check
    if check:
        if check.get("syntax_ok") is False or (check.get("new_high_or_critical") or 0) > 0:
            notes.append(IMPROVED_WARNING)
        elif check.get("syntax_ok") is None:
            notes.append("The syntax of the improved code could not be checked on this server.")
    if ctx.java_wrapped:
        notes.append(JAVA_WRAPPED)
    for item in ctx.ai_limitations:
        item = item.strip()
        if item:
            notes.append(f"AI note: {item}")
    # De-duplicate, keep order.
    return list(dict.fromkeys(notes))
