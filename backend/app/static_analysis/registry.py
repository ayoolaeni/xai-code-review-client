"""Which runners exist per language, and running them on one snippet (Section 8.5.1)."""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from app.pipeline import snippet as snippet_mod
from app.pipeline.types import StaticFinding, ToolRun
from app.static_analysis.bandit_runner import BanditRunner
from app.static_analysis.base import Runner
from app.static_analysis.eslint_runner import ESLintRunner
from app.static_analysis.pmd_runner import PMDRunner
from app.static_analysis.semgrep_runner import SemgrepRunner

log = logging.getLogger(__name__)

RUNNERS: dict[str, Runner] = {
    "semgrep": SemgrepRunner(),
    "bandit": BanditRunner(),
    "eslint": ESLintRunner(),
    "pmd": PMDRunner(),
}
LANGUAGE_TOOLS: dict[str, list[str]] = {
    "python": ["semgrep", "bandit"],
    "javascript": ["semgrep", "eslint"],
    "java": ["semgrep", "pmd"],
}


@dataclass
class StaticResult:
    findings: list[StaticFinding]
    tool_runs: list[ToolRun]
    wrapped: bool  # Java snippet was wrapped in a class


def tool_availability() -> dict[str, bool]:
    """Computed once and cached by each runner (shown in /api/health)."""
    return {name: runner.available() for name, runner in RUNNERS.items()}


def tool_versions() -> dict[str, str | None]:
    return {name: runner.version() for name, runner in RUNNERS.items()}


def _postprocess(
    raw: list[StaticFinding],
    prepared: snippet_mod.PreparedSnippet,
    extra: list[StaticFinding],
) -> list[StaticFinding]:
    tool_file_lines = prepared.text.count("\n") + 1
    wrapper_lines = (
        {prepared.header_lines + 1, tool_file_lines} if prepared.wrapped else set()
    )  # "public class Snippet {" and the closing "}"
    seen: set[tuple[str, str, int]] = set()
    out: list[StaticFinding] = []
    for f in raw:
        # Drop findings outside the file, or about the synthetic wrapper class itself.
        if not (1 <= f.start_line <= tool_file_lines) or f.start_line in wrapper_lines:
            continue
        f.start_line = prepared.map_line(f.start_line)
        f.end_line = max(f.start_line, prepared.map_line(f.end_line))
        key = (f.tool, f.rule_id, f.start_line)
        if key in seen:  # exact duplicate (same tool, rule and line)
            continue
        seen.add(key)
        out.append(f)
    out.extend(extra)
    out.sort(key=lambda f: (f.start_line, f.end_line, f.tool, f.rule_id))
    for i, f in enumerate(out, start=1):
        f.id = f"S{i}"
    return out


def run_static_analysis(
    code: str,
    language: str,
    enabled_tools: list[str],
    extra_findings: list[StaticFinding] | None = None,
) -> StaticResult:
    """Run the enabled tools for the language in parallel on the ORIGINAL code.

    SECURITY: never execute user code — the snippet is written to a temp file and only read by the tools.
    """
    prepared = snippet_mod.prepare(code, language)
    tools = [t for t in LANGUAGE_TOOLS.get(language, []) if t in enabled_tools]
    skipped = [t for t in LANGUAGE_TOOLS.get(language, []) if t not in enabled_tools]
    tool_runs: list[ToolRun] = []
    raw: list[StaticFinding] = []
    workdir = Path(tempfile.mkdtemp(prefix="xai-snippet-"))
    try:
        (workdir / prepared.filename).write_text(prepared.text, encoding="utf-8")

        def _run(name: str) -> tuple[list[StaticFinding], ToolRun]:
            start = time.monotonic()
            try:
                findings, run = RUNNERS[name].run(workdir, prepared.filename, language)
            except Exception as e:  # noqa: BLE001 - a tool must never fail the job
                log.exception("static tool crashed", extra={"tool": name})
                findings, run = [], ToolRun(
                    name, RUNNERS[name].version(), "failed", 0, f"{name} crashed: {e}"
                )
            log.info(
                "static tool finished",
                extra={
                    "event": "static_tool",
                    "tool": name,
                    "status": run.status,
                    "duration_ms": int((time.monotonic() - start) * 1000),
                    "count": run.findings_count,
                },
            )
            return findings, run

        if tools:
            with ThreadPoolExecutor(max_workers=len(tools)) as pool:
                for findings, run in pool.map(_run, tools):
                    raw.extend(findings)
                    tool_runs.append(run)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    for name in skipped:
        tool_runs.append(
            ToolRun(
                name,
                RUNNERS[name].version(),
                "skipped",
                0,
                "Disabled by the administrator.",
            )
        )
    findings = _postprocess(raw, prepared, list(extra_findings or []))
    # Keep the per-tool counts consistent with what survived de-duplication.
    for run in tool_runs:
        if run.status == "ok":
            run.findings_count = sum(1 for f in findings if f.tool == run.tool)
    return StaticResult(findings=findings, tool_runs=tool_runs, wrapped=prepared.wrapped)
