"""Check the AI's improved code without executing it (Section 8.17).

SECURITY: never execute user code. Python is parsed with `ast`, JavaScript with `node --check`
(parse only), Java with `javalang`.
"""

from __future__ import annotations

import ast
import re
import shutil
import tempfile
from pathlib import Path

from app.pipeline import taxonomy
from app.pipeline.snippet import prepare
from app.static_analysis.base import ToolTimeout, find_executable, run_tool, short_error
from app.static_analysis.registry import run_static_analysis

WARNING = "Automatic checks found problems in the improved code. Do not copy it without reviewing it."
_ESM_RE = re.compile(r"^\s*(import\s.+from\s|import\s*['\"{*]|export\s)", re.MULTILINE)


def syntax_check(code: str, language: str) -> tuple[bool | None, str | None]:
    """(syntax_ok, message). syntax_ok is None when the checker is unavailable."""
    if language == "python":
        try:
            ast.parse(code)  # parse only — never compile/exec
            return True, None
        except SyntaxError as e:
            return False, f"Line {e.lineno}: {e.msg}"
    if language == "javascript":
        node = find_executable("node")
        if not node:
            return (
                None,
                "Node.js is not installed on this server, so the syntax could not be checked.",
            )
        workdir = Path(tempfile.mkdtemp(prefix="xai-jscheck-"))
        try:
            name = "improved.mjs" if _ESM_RE.search(code) else "improved.cjs"
            (workdir / name).write_text(code, encoding="utf-8")
            res = run_tool([node, "--check", name], workdir, 30)  # --check parses without running
            if res.returncode == 0:
                return True, None
            lines = [ln for ln in res.stderr.splitlines() if ln.strip()]
            detail = next(
                (ln for ln in lines if "Error" in ln),
                lines[-1] if lines else "syntax error",
            )
            where = next((ln for ln in lines if name in ln), "")
            line_no = re.search(r":(\d+)", where)
            return False, (f"Line {line_no.group(1)}: " if line_no else "") + short_error(detail)
        except ToolTimeout:
            return None, "The JavaScript syntax check took too long."
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
    if language == "java":
        try:
            import javalang
        except ImportError:
            return (
                None,
                "The Java parser is not installed on this server, so the syntax could not be checked.",
            )
        prepared = prepare(code, "java")
        try:
            javalang.parse.parse(prepared.text)
            return True, None
        except javalang.parser.JavaSyntaxError as e:
            pos = getattr(getattr(e, "at", None), "position", None)
            line = prepared.map_line(pos.line) if pos else None
            return False, (f"Line {line}: " if line else "") + (e.description or "Java syntax error")
        except javalang.tokenizer.LexerError as e:
            return False, f"Java syntax error: {short_error(str(e))}"
        except Exception as e:  # noqa: BLE001 - javalang raises a few other error types on odd input
            return (
                False,
                f"Java syntax error: {short_error(str(e)) or type(e).__name__}",
            )
    return None, None


def verify(
    improved: str,
    language: str,
    enabled_tools: list[str],
    original_cwes: list[str | None],
) -> dict:
    ok, message = syntax_check(improved, language)
    check: dict = {
        "syntax_ok": ok,
        "syntax_message": message,
        "remaining_static_findings": None,
        "new_high_or_critical": None,
    }
    if ok is False:
        return check  # re-running the tools on code that does not parse is pointless
    result = run_static_analysis(improved, language, enabled_tools)
    original_families = {taxonomy.cwe_family(c) for c in original_cwes if c}
    new_serious = 0
    for f in result.findings:
        if f.category != "security" or not f.cwe_id:
            continue
        level = taxonomy.base_severity(f.cwe_id) or taxonomy.tool_level(f.tool, f.tool_severity)
        if level in ("HIGH", "CRITICAL") and taxonomy.cwe_family(f.cwe_id) not in original_families:
            new_serious += 1
    check["remaining_static_findings"] = len(result.findings)
    check["new_high_or_critical"] = new_serious
    return check


def has_problems(check: dict | None) -> bool:
    if not check:
        return False
    return check.get("syntax_ok") is False or (check.get("new_high_or_critical") or 0) > 0
