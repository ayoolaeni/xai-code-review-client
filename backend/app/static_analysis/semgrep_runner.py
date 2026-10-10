"""Semgrep runner (Section 8.5.2) — all languages."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.pipeline import taxonomy
from app.pipeline.types import StaticFinding, ToolRun
from app.static_analysis.base import ToolTimeout, find_executable, run_tool, short_error

RULES_DIR = Path(__file__).parent / "semgrep_rules"
RULE_FILES = {
    "python": "python.yml",
    "javascript": "javascript.yml",
    "java": "java.yml",
}
REGISTRY_PACKS = {"python": "p/python", "javascript": "p/javascript", "java": "p/java"}


def rule_id(check_id: str) -> str:
    """Vendored rules come back as '<path.dots>.xai-…'; keep only the rule ID for those."""
    last = check_id.rsplit(".", 1)[-1]
    return last if last.startswith("xai-") else check_id


def parse_output(stdout: str) -> list[StaticFinding]:
    data = json.loads(stdout)
    findings: list[StaticFinding] = []
    for r in data.get("results", []):
        extra = r.get("extra", {}) or {}
        meta = extra.get("metadata", {}) or {}
        cwe = taxonomy.normalise_cwe(meta.get("cwe"))
        owasp = taxonomy.normalise_owasp(meta.get("owasp")) or taxonomy.owasp_for_cwe(cwe)
        start = int(r.get("start", {}).get("line", 1))
        end = int(r.get("end", {}).get("line", start))
        findings.append(
            StaticFinding(
                id="",
                tool="semgrep",
                rule_id=rule_id(r.get("check_id", "semgrep")),
                message=(extra.get("message") or "").strip() or "Semgrep rule matched.",
                start_line=start,
                end_line=max(start, end),
                tool_severity=str(extra.get("severity", "WARNING")).upper(),
                cwe_id=cwe,
                owasp_category=owasp,
                category=taxonomy.semgrep_category(meta.get("category"), cwe),
            )
        )
    return findings


def _first_error(stdout: str) -> str:
    try:
        errors = json.loads(stdout).get("errors") or []
        text = str(errors[0].get("message", "")) if errors else ""
    except (json.JSONDecodeError, AttributeError):
        text = stdout
    return short_error(text or "unknown error")


class SemgrepRunner:
    name = "semgrep"
    languages = {"python", "javascript", "java"}

    def _bin(self) -> str | None:
        return find_executable("semgrep")

    def available(self) -> bool:
        return _semgrep_version() is not None

    def version(self) -> str | None:
        return _semgrep_version()

    def _command(self, filename: str, language: str, registry: bool) -> list[str]:
        args = [
            self._bin() or "semgrep",
            "scan",
            "--json",
            "--quiet",
            "--metrics=off",
            "--disable-version-check",
            "--config",
            str(RULES_DIR / RULE_FILES[language]),
        ]
        if registry:
            args += ["--config", REGISTRY_PACKS[language], "--config", "p/secrets"]
        # semgrep-core reserves more address space than RLIMIT_AS allows and is killed under it,
        # so memory is bounded with Semgrep's own limit instead (in MB).
        args += ["--timeout", "20", "--max-memory", "1500", filename]
        return args

    def run(self, workdir: Path, filename: str, language: str) -> tuple[list[StaticFinding], ToolRun]:
        if not self.available():
            return [], ToolRun(
                self.name,
                None,
                "unavailable",
                0,
                "Semgrep is not installed on this server.",
            )
        settings = get_settings()
        timeout = settings.STATIC_TOOL_TIMEOUT_SECONDS
        use_registry = settings.SEMGREP_USE_REGISTRY
        message = None
        try:
            cmd = self._command(filename, language, use_registry)
            result = run_tool(cmd, workdir, timeout, limit_memory=False)
            ok = result.returncode in (0, 1) and result.stdout.strip().startswith("{")
            if use_registry and not ok:
                # Registry rules could not be fetched (e.g. no internet): fall back to vendored rules.
                cmd = self._command(filename, language, False)
                result = run_tool(cmd, workdir, timeout, limit_memory=False)
                message = "Registry rules unavailable; used built-in rules only."
            if result.returncode not in (0, 1):
                # Semgrep reports fatal problems (invalid rules, engine killed) as JSON errors with exit code ≥ 2.
                return [], ToolRun(
                    self.name, self.version(), "failed", 0, f"Semgrep failed: {_first_error(result.stdout)}"
                )
            findings = parse_output(result.stdout)
        except ToolTimeout:
            return [], ToolRun(
                self.name,
                self.version(),
                "timeout",
                0,
                "Semgrep took too long and was stopped.",
            )
        except (json.JSONDecodeError, ValueError, OSError) as e:
            detail = short_error(getattr(e, "msg", "") or str(e))
            return [], ToolRun(self.name, self.version(), "failed", 0, f"Semgrep failed: {detail}")
        return findings, ToolRun(self.name, self.version(), "ok", len(findings), message)


@lru_cache(maxsize=1)
def _semgrep_version() -> str | None:
    exe = find_executable("semgrep")
    if not exe:
        return None
    try:
        res = run_tool(
            [exe, "--version", "--disable-version-check"],
            Path.cwd(),
            60,
            limit_memory=False,
        )
    except (ToolTimeout, OSError):
        return None
    m = re.search(r"\d+\.\d+\.\d+", res.stdout + res.stderr)
    return m.group(0) if (res.returncode == 0 and m) else None
