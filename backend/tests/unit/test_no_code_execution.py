"""Static scan of the backend for calls that could execute user code (Section 12.1, NFR5)."""

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"

# Files allowed to start subprocesses (the hardened runner helper and tool-version probes).
SUBPROCESS_ALLOWED = {"static_analysis/base.py"}

FORBIDDEN = [
    (re.compile(r"(?<![\w.])exec\s*\("), "exec("),
    (re.compile(r"(?<![\w.])eval\s*\("), "eval("),
    (re.compile(r"\bos\.system\s*\("), "os.system("),
    (re.compile(r"\bos\.popen\s*\("), "os.popen("),
    (re.compile(r"shell\s*=\s*True"), "shell=True"),
    (re.compile(r"\bcompile\s*\([^)]*['\"]exec['\"]"), "compile(..., 'exec')"),
    (
        re.compile(r"\bimportlib\.import_module\s*\(\s*(code|user|snippet)"),
        "dynamic import of user input",
    ),
]


def _code_lines(path: Path):
    """Yield (number, line) without comments and string-only lines (rewrite patterns live in strings)."""
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Remove string literals so regex patterns and messages that *mention* eval( are not flagged.
        no_strings = re.sub(r"r?(['\"])(?:\\.|(?!\1).)*\1", '""', line)
        yield n, no_strings.split("#", 1)[0]


def test_no_forbidden_calls():
    problems = []
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP).as_posix()
        for n, line in _code_lines(path):
            for pattern, name in FORBIDDEN:
                if pattern.search(line):
                    problems.append(f"{rel}:{n}: {name}")
    assert problems == [], "Forbidden calls found:\n" + "\n".join(problems)


def test_subprocess_only_in_runner_helper():
    offenders = []
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP).as_posix()
        text = path.read_text(encoding="utf-8")
        if (
            re.search(r"^\s*(import subprocess|from subprocess import)", text, re.MULTILINE)
            and rel not in SUBPROCESS_ALLOWED
        ):
            offenders.append(rel)
    assert offenders == [], f"subprocess used outside {SUBPROCESS_ALLOWED}: {offenders}"


def test_runner_uses_shell_false_and_timeout():
    text = (APP / "static_analysis" / "base.py").read_text(encoding="utf-8")
    assert "shell=False" in text and "timeout=timeout" in text


def test_security_comments_mark_user_code_handling():
    hits = sum(
        "SECURITY: never execute user code" in p.read_text(encoding="utf-8") for p in APP.rglob("*.py")
    )
    assert hits >= 5
