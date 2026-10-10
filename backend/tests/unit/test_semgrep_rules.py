"""One positive and one negative example per vendored Semgrep rule (Section 8.5.6).

Runs only where Semgrep is installed (Linux / Docker): `pytest -m tools`.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.static_analysis.base import find_executable, run_tool
from app.static_analysis.semgrep_runner import RULES_DIR, rule_id

pytestmark = [
    pytest.mark.tools,
    pytest.mark.skipif(find_executable("semgrep") is None, reason="Semgrep not installed"),
]

EXT = {"python": "py", "javascript": "js", "java": "java"}

CASES: list[tuple[str, str, str, str]] = [
    # (language, rule, positive example, negative example)
    (
        "python",
        "xai-py-sql-string-concat",
        'def f(cur, name):\n    q = "SELECT * FROM u WHERE n = \'" + name + "\'"\n    cur.execute(q)\n',
        'def f(cur, name):\n    cur.execute("SELECT * FROM u WHERE n = ?", (name,))\n',
    ),
    (
        "python",
        "xai-py-os-system",
        "import os\ndef f(h):\n    os.system('ping ' + h)\n",
        "import os\nos.system('ls')\n",
    ),
    (
        "python",
        "xai-py-pickle-loads",
        "import pickle\ndef f(d):\n    return pickle.loads(d)\n",
        "import json\ndef f(d):\n    return json.loads(d)\n",
    ),
    (
        "python",
        "xai-py-eval",
        "def f(x):\n    return eval(x)\n",
        "def f(x):\n    return int(x)\n",
    ),
    (
        "python",
        "xai-py-weak-hash",
        "import hashlib\nh = hashlib.md5(b'x')\n",
        "import hashlib\nh = hashlib.sha256(b'x')\n",
    ),
    (
        "python",
        "xai-py-path-join-user-input",
        "import os\ndef f(name):\n    path = os.path.join('/srv', name)\n    return open(path).read()\n",
        "import os\ndef f():\n    return open(os.path.join('/srv', 'fixed.txt')).read()\n",
    ),
    (
        "python",
        "xai-py-mutable-default",
        "def f(a=[]):\n    return a\n",
        "def f(a=None):\n    return a\n",
    ),
    (
        "python",
        "xai-py-bare-except",
        "try:\n    x = 1\nexcept:\n    pass\n",
        "try:\n    x = 1\nexcept ValueError:\n    pass\n",
    ),
    (
        "javascript",
        "xai-js-innerhtml",
        "function f(c) { document.getElementById('a').innerHTML = c; }\n",
        "function f(c) { document.getElementById('a').textContent = c; }\n",
    ),
    (
        "javascript",
        "xai-js-eval",
        "function f(x) { return eval(x); }\n",
        "function f(x) { return Number(x); }\n",
    ),
    (
        "javascript",
        "xai-js-child-process",
        "const { exec } = require('child_process');\nfunction f(n) { exec(`convert ${n} out.png`); }\n",
        "const { execFile } = require('child_process');\nfunction f(n) { execFile('convert', [n]); }\n",
    ),
    (
        "javascript",
        "xai-js-sql-concat",
        "function f(db, id) { return db.query('SELECT * FROM o WHERE id = ' + id); }\n",
        "function f(db, id) { return db.query('SELECT * FROM o WHERE id = ?', [id]); }\n",
    ),
    (
        "javascript",
        "xai-js-hardcoded-jwt-secret",
        "const jwt = require('jsonwebtoken');\nfunction f(p) { return jwt.sign(p, 'supersecret'); }\n",
        "const jwt = require('jsonwebtoken');\nfunction f(p) { return jwt.sign(p, process.env.JWT_SECRET); }\n",
    ),
    (
        "javascript",
        "xai-js-path-traversal",
        "app.get('/f/:n', (req, res) => { res.sendFile(path.join(__dirname, req.params.n)); });\n",
        "app.get('/f', (req, res) => { res.sendFile('/srv/index.html'); });\n",
    ),
    (
        "javascript",
        "xai-js-math-random-token",
        "function createResetToken() { return Math.random().toString(36).slice(2); }\n",
        "function shuffleCards(cards) { return cards.sort(() => Math.random() - 0.5); }\n",
    ),
    (
        "javascript",
        "xai-js-prototype-pollution",
        "function merge(t, s) {\n  for (const k in s) {\n    if (typeof s[k] === 'object') { merge(t[k], s[k]); }\n"
        "    else { t[k] = s[k]; }\n  }\n  return t;\n}\n",
        "function merge(t, s) {\n  for (const k in s) {\n    if (k === '__proto__' || k === 'constructor') { continue; }\n"
        "    t[k] = s[k];\n  }\n  return t;\n}\n",
    ),
    (
        "java",
        "xai-java-sql-concat",
        "class A { void f(java.sql.Statement st, String n) throws Exception {\n"
        '  String q = "SELECT * FROM u WHERE n = \'" + n + "\'";\n  st.executeQuery(q);\n} }\n',
        "class A { void f(java.sql.Connection c, String n) throws Exception {\n"
        '  java.sql.PreparedStatement p = c.prepareStatement("SELECT * FROM u WHERE n = ?");\n'
        "  p.setString(1, n);\n  p.executeQuery();\n} }\n",
    ),
    (
        "java",
        "xai-java-runtime-exec",
        'class A { void f(String d) throws Exception { Runtime.getRuntime().exec("tar czf b.tgz " + d); } }\n',
        'class A { void f() throws Exception { Runtime.getRuntime().exec("ls"); } }\n',
    ),
    (
        "java",
        "xai-java-hardcoded-password",
        'class A { private static final String DB_PASSWORD = "S3cret!"; }\n',
        'class A { private static final String DB_USER = "app"; }\n',
    ),
    (
        "java",
        "xai-java-object-input-stream",
        "class A { Object f(java.io.InputStream in) throws Exception {\n"
        "  java.io.ObjectInputStream o = new java.io.ObjectInputStream(in);\n  return o.readObject();\n} }\n",
        "class A { Object f(java.io.InputStream in) throws Exception { return in.read(); } }\n",
    ),
    (
        "java",
        "xai-java-path-traversal",
        "class A { java.io.File f(String base, String name) { return new java.io.File(base + name); } }\n",
        'class A { java.io.File f(String base) { return new java.io.File(base + "/index.html"); } }\n',
    ),
    (
        "java",
        "xai-java-weak-crypto",
        'class A { void f() throws Exception { java.security.MessageDigest.getInstance("MD5"); } }\n',
        'class A { void f() throws Exception { java.security.MessageDigest.getInstance("SHA-256"); } }\n',
    ),
    (
        "java",
        "xai-java-xxe",
        "import javax.xml.parsers.*;\nclass A { void f() throws Exception {\n"
        "  DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();\n  dbf.newDocumentBuilder();\n} }\n",
        "import javax.xml.parsers.*;\nclass A { void f() throws Exception {\n"
        "  DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();\n"
        '  dbf.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);\n'
        "  dbf.newDocumentBuilder();\n} }\n",
    ),
    (
        "java",
        "xai-java-empty-catch",
        "class A { void f() { try { g(); } catch (Exception e) { } } void g() {} }\n",
        "class A { void f() { try { g(); } catch (Exception e) { throw new RuntimeException(e); } } void g() {} }\n",
    ),
]


def _scan(language: str, code: str) -> set[str]:
    with tempfile.TemporaryDirectory() as d:
        name = f"Sample.{EXT[language]}" if language == "java" else f"sample.{EXT[language]}"
        (Path(d) / name).write_text(code, encoding="utf-8")
        args = [
            find_executable("semgrep"),
            "scan",
            "--json",
            "--quiet",
            "--metrics=off",
            "--disable-version-check",
            "--config",
            str(RULES_DIR / f"{language}.yml"),
            name,
        ]
        res = run_tool(args, Path(d), 120)
        data = json.loads(res.stdout)
        assert not [e for e in data.get("errors", []) if e.get("level") == "error"], data["errors"]
        return {rule_id(r["check_id"]) for r in data["results"]}


@pytest.mark.parametrize("language", ["python", "javascript", "java"])
def test_rule_files_validate(language):
    res = run_tool(
        [
            find_executable("semgrep"),
            "scan",
            "--validate",
            "--metrics=off",
            "--config",
            str(RULES_DIR / f"{language}.yml"),
        ],
        RULES_DIR,
        120,
    )
    assert res.returncode == 0, res.stdout + res.stderr


@pytest.mark.parametrize("language,rule,positive,negative", CASES, ids=[c[1] for c in CASES])
def test_rule_positive_and_negative(language, rule, positive, negative):
    assert rule in _scan(language, positive), f"{rule} did not match its positive example"
    assert rule not in _scan(language, negative), f"{rule} matched its negative example"
