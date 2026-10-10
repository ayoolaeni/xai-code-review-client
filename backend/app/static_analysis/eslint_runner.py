"""ESLint 9 + eslint-plugin-security runner (Section 8.5.4) — JavaScript."""

from __future__ import annotations

import json
import shutil
import uuid
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.pipeline import taxonomy
from app.pipeline.types import StaticFinding, ToolRun
from app.static_analysis.base import ToolTimeout, find_executable, run_tool, short_error


class ESLintParseError(Exception):
    pass


def parse_output(stdout: str) -> list[StaticFinding]:
    data = json.loads(stdout)
    if not data:
        return []
    findings: list[StaticFinding] = []
    for m in data[0].get("messages", []):
        rule = m.get("ruleId")
        if rule is None:
            if m.get("fatal"):
                raise ESLintParseError(m.get("message", "parse error"))
            continue
        cwe = taxonomy.ESLINT_CWE.get(rule)
        start = int(m.get("line") or 1)
        end = int(m.get("endLine") or start)
        findings.append(
            StaticFinding(
                id="",
                tool="eslint",
                rule_id=rule,
                message=(m.get("message") or rule).strip(),
                start_line=start,
                end_line=max(start, end),
                tool_severity=str(m.get("severity", 1)),
                cwe_id=cwe,
                owasp_category=taxonomy.owasp_for_cwe(cwe),
                category=taxonomy.eslint_category(rule),
            )
        )
    return findings


class ESLintRunner:
    name = "eslint"
    languages = {"javascript"}

    def available(self) -> bool:
        return _eslint_version() is not None

    def version(self) -> str | None:
        return _eslint_version()

    def run(self, workdir: Path, filename: str, language: str) -> tuple[list[StaticFinding], ToolRun]:
        if not self.available():
            return [], ToolRun(
                self.name,
                None,
                "unavailable",
                0,
                "ESLint is not installed on this server (needs Node.js).",
            )
        eslint_dir = get_settings().eslint_dir
        timeout = get_settings().STATIC_TOOL_TIMEOUT_SECONDS
        # ESLint 9 ignores files outside its base directory, so copy the snippet under ESLINT_DIR/work.
        job_dir = eslint_dir / "work" / uuid.uuid4().hex
        try:
            job_dir.mkdir(parents=True, exist_ok=False)
            target = job_dir / Path(filename).name
            shutil.copyfile(workdir / filename, target)
            rel = target.relative_to(eslint_dir).as_posix()
            args = [
                find_executable("node") or "node",
                "node_modules/eslint/bin/eslint.js",
                "--config",
                "eslint.config.mjs",
                "--format",
                "json",
                "--no-warn-ignored",
                rel,
            ]
            res = run_tool(args, eslint_dir, timeout)
            # Exit code 1 = problems found (not a failure); 2 = configuration or internal error.
            if res.returncode not in (0, 1) or not res.stdout.strip().startswith("["):
                raise ValueError(short_error(res.stderr or res.stdout) or f"exit code {res.returncode}")
            findings = parse_output(res.stdout)
        except ToolTimeout:
            return [], ToolRun(
                self.name,
                self.version(),
                "timeout",
                0,
                "ESLint took too long and was stopped.",
            )
        except ESLintParseError as e:
            return [], ToolRun(
                self.name,
                self.version(),
                "failed",
                0,
                f"ESLint could not parse the code: {e}",
            )
        except (json.JSONDecodeError, ValueError, OSError) as e:
            return [], ToolRun(
                self.name,
                self.version(),
                "failed",
                0,
                f"ESLint failed: {short_error(str(e))}",
            )
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)
        return findings, ToolRun(self.name, self.version(), "ok", len(findings), None)


@lru_cache(maxsize=1)
def _eslint_version() -> str | None:
    eslint_dir = get_settings().eslint_dir
    pkg = eslint_dir / "node_modules" / "eslint" / "package.json"
    plugin = eslint_dir / "node_modules" / "eslint-plugin-security" / "package.json"
    if not (find_executable("node") and pkg.is_file() and plugin.is_file()):
        return None
    try:
        return json.loads(pkg.read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError):
        return None
