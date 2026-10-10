"""PMD 7 runner (Section 8.5.5) — Java."""

from __future__ import annotations

import json
import re
import shutil
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.pipeline import taxonomy
from app.pipeline.types import StaticFinding, ToolRun
from app.static_analysis.base import ToolTimeout, run_tool, short_error

RULESET = Path(__file__).parent / "pmd" / "ruleset.xml"


class PMDProcessingError(Exception):
    pass


def parse_output(stdout: str) -> list[StaticFinding]:
    data = json.loads(stdout)
    files = data.get("files", [])
    if not files and data.get("processingErrors"):
        err = data["processingErrors"][0]
        raise PMDProcessingError(short_error(err.get("message", "processing error")))
    findings: list[StaticFinding] = []
    for v in files[0].get("violations", []) if files else []:
        rule = v.get("rule", "PMD")
        cwe = taxonomy.PMD_CWE.get(rule)
        start = int(v.get("beginline", 1))
        end = int(v.get("endline", start))
        findings.append(
            StaticFinding(
                id="",
                tool="pmd",
                rule_id=rule,
                message=(v.get("description") or rule).strip(),
                start_line=start,
                end_line=max(start, end),
                tool_severity=str(v.get("priority", 3)),
                cwe_id=cwe,
                owasp_category=taxonomy.owasp_for_cwe(cwe),
                category=taxonomy.pmd_category(v.get("ruleset", "")),
            )
        )
    return findings


def _pmd_bin() -> str | None:
    configured = get_settings().PMD_BIN
    if not configured:
        return None
    path = Path(configured)
    for candidate in (path, path.with_suffix(".bat"), path.with_suffix(".cmd")):
        if candidate.is_file():
            return str(candidate)
    return shutil.which(configured)


class PMDRunner:
    name = "pmd"
    languages = {"java"}

    def available(self) -> bool:
        return _pmd_version() is not None

    def version(self) -> str | None:
        return _pmd_version()

    def run(self, workdir: Path, filename: str, language: str) -> tuple[list[StaticFinding], ToolRun]:
        if not self.available():
            return [], ToolRun(
                self.name,
                None,
                "unavailable",
                0,
                "PMD is not installed on this server (needs Java 17).",
            )
        timeout = get_settings().STATIC_TOOL_TIMEOUT_SECONDS
        args = [
            _pmd_bin(),
            "check",
            "--no-cache",
            "--no-progress",
            "-d",
            filename,
            "-R",
            str(RULESET),
            "-f",
            "json",
        ]
        try:
            # The JVM reserves a lot of virtual memory, so the address-space limit is not applied to PMD.
            res = run_tool(args, workdir, timeout + 30, limit_memory=False)
            # Exit code 4 = violations found; 5 = recoverable errors (e.g. parse error) — both still give JSON.
            out = res.stdout[res.stdout.find("{") :] if "{" in res.stdout else ""
            if res.returncode not in (0, 4, 5) or not out:
                raise ValueError(short_error(res.stderr or res.stdout) or f"exit code {res.returncode}")
            findings = parse_output(out)
        except ToolTimeout:
            return [], ToolRun(
                self.name,
                self.version(),
                "timeout",
                0,
                "PMD took too long and was stopped.",
            )
        except PMDProcessingError as e:
            return [], ToolRun(
                self.name,
                self.version(),
                "failed",
                0,
                f"PMD could not parse the code: {e}",
            )
        except (json.JSONDecodeError, ValueError, OSError) as e:
            return [], ToolRun(
                self.name,
                self.version(),
                "failed",
                0,
                f"PMD failed: {short_error(str(e))}",
            )
        return findings, ToolRun(self.name, self.version(), "ok", len(findings), None)


@lru_cache(maxsize=1)
def _pmd_version() -> str | None:
    exe = _pmd_bin()
    if not exe:
        return None
    try:
        res = run_tool([exe, "--version"], Path.cwd(), 90, limit_memory=False)
    except (ToolTimeout, OSError):
        return None
    m = re.search(r"PMD\s+(\d+\.\d+\.\d+)", res.stdout + res.stderr)
    return m.group(1) if (res.returncode == 0 and m) else None
