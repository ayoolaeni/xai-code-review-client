"""Bandit runner (Section 8.5.3) — Python."""

from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.pipeline import taxonomy
from app.pipeline.types import StaticFinding, ToolRun
from app.static_analysis.base import ToolTimeout, run_tool, short_error


def parse_output(stdout: str) -> list[StaticFinding]:
    data = json.loads(stdout)
    findings: list[StaticFinding] = []
    for r in data.get("results", []):
        test_id = r.get("test_id", "B000")
        cwe_obj = r.get("issue_cwe") or {}
        tool_cwe = taxonomy.normalise_cwe(cwe_obj.get("id")) if isinstance(cwe_obj, dict) else None
        # The project's curated map (8.6.3) wins: Bandit labels eval (B307) as CWE-78 and
        # try/except/pass (B110) as CWE-703, which do not describe those weaknesses.
        cwe = taxonomy.BANDIT_CWE.get(test_id) or tool_cwe
        start = int(r.get("line_number", 1))
        line_range = r.get("line_range") or [start]
        findings.append(
            StaticFinding(
                id="",
                tool="bandit",
                rule_id=test_id,
                message=(r.get("issue_text") or r.get("test_name") or "Bandit issue").strip(),
                start_line=start,
                end_line=max([start, *line_range]),
                tool_severity=str(r.get("issue_severity", "MEDIUM")).upper(),
                cwe_id=cwe,
                owasp_category=taxonomy.owasp_for_cwe(cwe),
                category=taxonomy.category_for_cwe(cwe, default="security"),
            )
        )
    return findings


class BanditRunner:
    name = "bandit"
    languages = {"python"}

    def available(self) -> bool:
        return _bandit_version() is not None

    def version(self) -> str | None:
        return _bandit_version()

    def run(self, workdir: Path, filename: str, language: str) -> tuple[list[StaticFinding], ToolRun]:
        if not self.available():
            return [], ToolRun(
                self.name,
                None,
                "unavailable",
                0,
                "Bandit is not installed on this server.",
            )
        timeout = get_settings().STATIC_TOOL_TIMEOUT_SECONDS
        try:
            res = run_tool(
                [sys.executable, "-m", "bandit", "-f", "json", "-q", "-r", filename],
                workdir,
                timeout,
            )
            # Exit code 1 means "issues found" — not a failure.
            if res.returncode not in (0, 1):
                raise ValueError(short_error(res.stderr or res.stdout) or f"exit code {res.returncode}")
            findings = parse_output(res.stdout)
        except ToolTimeout:
            return [], ToolRun(
                self.name,
                self.version(),
                "timeout",
                0,
                "Bandit took too long and was stopped.",
            )
        except (json.JSONDecodeError, ValueError, OSError) as e:
            return [], ToolRun(
                self.name,
                self.version(),
                "failed",
                0,
                f"Bandit failed: {short_error(str(e))}",
            )
        return findings, ToolRun(self.name, self.version(), "ok", len(findings), None)


@lru_cache(maxsize=1)
def _bandit_version() -> str | None:
    try:
        from importlib.metadata import version

        return version("bandit")
    except Exception:  # noqa: BLE001
        pass
    try:
        res = run_tool(
            [sys.executable, "-m", "bandit", "--version"],
            Path.cwd(),
            60,
            limit_memory=False,
        )
    except (ToolTimeout, OSError):
        return None
    m = re.search(r"\d+\.\d+\.\d+", res.stdout)
    return m.group(0) if m else None
