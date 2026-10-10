"""Improved-code checks without execution (Section 8.17)."""

import pytest

from app.pipeline.verify_improved import has_problems, syntax_check, verify
from app.static_analysis.base import find_executable


def test_python_syntax():
    assert syntax_check("def f(x):\n    return x\n", "python") == (True, None)
    ok, msg = syntax_check("def f(x)\n    return x\n", "python")
    assert ok is False and msg.startswith("Line 1")


@pytest.mark.skipif(find_executable("node") is None, reason="Node.js not installed")
def test_javascript_syntax():
    assert syntax_check("function f(a) { return a + 1; }\nmodule.exports = { f };", "javascript") == (
        True,
        None,
    )
    assert syntax_check("import x from 'y';\nexport const z = x;", "javascript")[0] is True
    ok, msg = syntax_check("function f( { return 1; }", "javascript")
    assert ok is False and msg


def test_javascript_never_runs_code(tmp_path):
    marker = tmp_path / "ran.txt"
    code = f"require('fs').writeFileSync({str(marker)!r}, 'x');"
    if find_executable("node"):
        assert syntax_check(code, "javascript")[0] is True
    assert not marker.exists()  # --check parses only


def test_java_syntax():
    assert syntax_check("public class A { int f() { return 1; } }", "java") == (
        True,
        None,
    )
    assert syntax_check("int f() { return 1; }", "java") == (
        True,
        None,
    )  # wrapped snippet
    ok, msg = syntax_check("public class A { int f() { return 1 } }", "java")
    assert ok is False and msg


def test_verify_skips_tools_on_syntax_error():
    check = verify("def f(:\n", "python", ["bandit"], [])
    assert check["syntax_ok"] is False and check["remaining_static_findings"] is None
    assert has_problems(check)


def test_verify_counts_new_serious_findings():
    code = "import os\n\ndef f(h):\n    os.system('ping ' + h)\n"
    check = verify(code, "python", ["bandit"], ["CWE-89"])
    if check["remaining_static_findings"]:  # Bandit installed
        assert check["new_high_or_critical"] >= 1 and has_problems(check)
    clean = verify(code, "python", ["bandit"], ["CWE-78"])
    assert clean["new_high_or_critical"] == 0
