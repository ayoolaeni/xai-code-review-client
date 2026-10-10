"""Build the prompts of Section 8.7 from pipeline data."""

from __future__ import annotations

from app.llm.output_schema import ExplanationOutput, RiskOnlyOutput
from app.llm.prompts import registry
from app.pipeline.language import LABELS
from app.pipeline.snippet import format_numbered
from app.pipeline.types import StaticFinding


def static_findings_block(findings: list[StaticFinding]) -> str:
    """One line per finding: `S3 | bandit B608 | lines 6-7 | CWE-89 | message` or `(none)`."""
    if not findings:
        return "(none)"
    lines = []
    for f in findings:
        message = " ".join(f.message.split())  # one line
        lines.append(
            f"{f.id} | {f.tool} {f.rule_id} | lines {f.start_line}-{f.end_line} | {f.cwe_id or 'no CWE'} | {message}"
        )
    return "\n".join(lines)


def system_prompt(version: str) -> str:
    return registry.load(version, "system")


def explain_prompt(
    redacted_code: str,
    language: str,
    static_findings: list[StaticFinding],
    version: str,
) -> str:
    # SECURITY: the code is sent as numbered DATA between delimiters; it is never executed.
    return registry.render(
        version,
        "explain_user",
        language_label=LABELS[language],
        line_count=redacted_code.count("\n") + 1,
        numbered_code=format_numbered(redacted_code),
        static_findings_block=static_findings_block(static_findings),
        json_schema=registry.json_schema_text(ExplanationOutput),
    )


def risks_prompt(redacted_code: str, language: str, version: str) -> str:
    return registry.render(
        version,
        "risks_only_user",
        language_label=LABELS[language],
        line_count=redacted_code.count("\n") + 1,
        numbered_code=format_numbered(redacted_code),
        json_schema=registry.json_schema_text(RiskOnlyOutput),
    )


def baseline_prompt(code: str, language: str, version: str) -> str:
    return registry.render(version, "baseline_user", language_label=LABELS[language], code=code)
