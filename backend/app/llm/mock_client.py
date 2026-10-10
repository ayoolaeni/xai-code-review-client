"""Deterministic offline mock provider (Section 8.9.4).

It reads the same prompts a real model would get and returns schema-valid, sensible JSON so the whole
application, the tests and demos run without an API key. It never executes the code it receives.
"""

from __future__ import annotations

import json
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass

from pydantic import BaseModel

from app.llm.client import LLMError, LLMResult
from app.pipeline import taxonomy
from app.pipeline.recommendations import CONSEQUENCES, recommendation_for
from app.pipeline.review_rule import detect_domains

MOCK_MODEL = "mock-v1"
MOCK_LIMITATION = "This explanation was produced by the offline mock provider and is far less detailed than a real language model."

# ---------- prompt parsing ----------
_NUMBERED_RE = re.compile(
    r"=== NUMBERED CODE \(lines 1 to (\d+)\) ===\n(.*?)\n=== END OF CODE ===", re.DOTALL
)
_STATIC_RE = re.compile(
    r"=== STATIC ANALYSIS FINDINGS[^\n]*\n(.*?)\n=== END OF STATIC FINDINGS ===",
    re.DOTALL,
)
_LANG_RE = re.compile(r"^(?:Analyse|Review) the following (\w+) code", re.MULTILINE)
_BASELINE_RE = re.compile(r"^Explain this (\w+) code and point out any problems\.\n\n(.*)$", re.DOTALL)
_STATIC_LINE_RE = re.compile(r"^(S\d+) \| (\S+) (.+?) \| lines (\d+)-(\d+) \| ([^|]+?) \| (.*)$")
LABEL_TO_LANG = {"python": "python", "javascript": "javascript", "java": "java"}


def unnumber(numbered: str) -> str:
    return "\n".join(re.sub(r"^\s*\d+ \| ?", "", ln, count=1) for ln in numbered.split("\n"))


@dataclass
class StaticRef:
    id: str
    tool: str
    rule: str
    start: int
    end: int
    cwe: str | None
    message: str


def parse_static_block(block: str) -> list[StaticRef]:
    refs: list[StaticRef] = []
    for line in block.strip().split("\n"):
        m = _STATIC_LINE_RE.match(line.strip())
        if m:
            cwe = taxonomy.normalise_cwe(m.group(6))
            refs.append(
                StaticRef(
                    m.group(1),
                    m.group(2),
                    m.group(3),
                    int(m.group(4)),
                    int(m.group(5)),
                    cwe,
                    m.group(7).strip(),
                )
            )
    return refs


# ---------- code structure (breakdown) ----------
_PY_DEF = re.compile(r"^(?:async\s+)?(def|class)\s+(\w+)")
_JS_DEF = re.compile(
    r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\s*\*?\s*(\w+)|class\s+(\w+)"
    r"|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>|\w+\s*=>))"
)
_JS_CALLBACK = re.compile(
    r"^(\w+)\.(get|post|put|patch|delete|use|addEventListener|on)\(\s*(['\"`][^'\"`]*['\"`])?"
)
_JAVA_METHOD = re.compile(
    r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:public|private|protected|static|final|synchronized|abstract|native|default)\s+)*"
    r"(?:<[^>]+>\s+)?(?:[\w.$]+(?:<[^>]*>)?(?:\[\])*\s+)?(\w+)\s*\([^;{]*\)?\s*(?:throws\s+[\w.,\s]+)?\{?\s*$"
)
_JAVA_KEYWORDS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "new",
    "else",
    "try",
    "do",
    "synchronized",
    "throw",
}
_JAVA_CLASS = re.compile(r"\b(class|interface|enum|record)\s+(\w+)")


@dataclass
class Block:
    start: int
    end: int
    kind: str  # function | class | method | constructor | handler
    name: str


def _brace_end(lines: list[str], start_idx: int) -> int:
    """Index of the line where the brace block opened at/after start_idx closes."""
    depth = 0
    opened = False
    for i in range(start_idx, len(lines)):
        line = re.sub(r"(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`[^`]*`)", '""', lines[i])
        line = line.split("//", 1)[0]
        for ch in line:
            if ch == "{":
                depth += 1
                opened = True
            elif ch == "}":
                depth -= 1
        if opened and depth <= 0:
            return i
        if not opened and i > start_idx + 3:
            break
        if not opened and lines[i].rstrip().endswith(";"):
            return i
    return start_idx


def _python_blocks(lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        m = _PY_DEF.match(lines[i])
        if m:
            start = i
            while start > 0 and lines[start - 1].startswith("@"):
                start -= 1
            j = i + 1
            last = i
            while j < len(lines):
                if lines[j].strip() and not lines[j][0].isspace():
                    break
                if lines[j].strip():
                    last = j
                j += 1
            blocks.append(
                Block(
                    start + 1,
                    last + 1,
                    "class" if m.group(1) == "class" else "function",
                    m.group(2),
                )
            )
            i = last + 1
            continue
        i += 1
    return blocks


def _js_blocks(lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        m = _JS_DEF.match(lines[i])
        cb = _JS_CALLBACK.match(lines[i]) if not m else None
        if m or cb:
            end = _brace_end(lines, i)
            if m:
                name = m.group(1) or m.group(2) or m.group(3)
                kind = "class" if m.group(2) else "function"
            else:
                route = (cb.group(3) or "").strip("'\"`")
                name = f"{cb.group(1)}.{cb.group(2)}({route})" if route else f"{cb.group(1)}.{cb.group(2)}"
                kind = "handler"
            blocks.append(Block(i + 1, end + 1, kind, name))
            i = end + 1
            continue
        i += 1
    return blocks


def _java_blocks(lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    class_names = {m.group(2) for ln in lines for m in [_JAVA_CLASS.search(ln)] if m}
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _JAVA_METHOD.match(line)
        if (
            m
            and m.group(1) not in _JAVA_KEYWORDS
            and "=" not in line.split("(")[0]
            and not _JAVA_CLASS.search(line)
        ):
            start = i
            while start > 0 and lines[start - 1].strip().startswith("@"):
                start -= 1
            end = _brace_end(lines, i)
            if end > i or lines[i].rstrip().endswith("}"):
                kind = "constructor" if m.group(1) in class_names else "method"
                blocks.append(Block(start + 1, end + 1, kind, m.group(1)))
                i = end + 1
                continue
        i += 1
    return blocks


def find_blocks(code: str, language: str) -> list[Block]:
    lines = code.split("\n")
    if language == "python":
        return _python_blocks(lines)
    if language == "javascript":
        return _js_blocks(lines)
    return _java_blocks(lines)


_CALL_RE = re.compile(r"\b([A-Za-z_][\w.]*)\s*\(")
_CALL_SKIP = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "function",
    "def",
    "class",
    "print",
    "elif",
    "super",
    "new",
    "typeof",
    "with",
    "except",
    "and",
    "or",
    "not",
    "in",
    "is",
}


def _calls(text: str, own_name: str) -> list[str]:
    out: list[str] = []
    for m in _CALL_RE.finditer(text):
        name = m.group(1)
        if name in _CALL_SKIP or name == own_name or name.split(".")[-1] in _CALL_SKIP:
            continue
        if name not in out:
            out.append(name)
    return out[:5]


def _doc_of(lines: list[str], block: Block) -> str | None:
    """First docstring / comment line of a block (or the comment right above it)."""
    body = lines[block.start - 1 : block.end]
    for ln in body[1:4]:
        s = ln.strip()
        m = re.match(r'^(?:"""|\'\'\'|/\*\*?|\*|//|#)\s*(.+?)\s*(?:"""|\'\'\'|\*/)?$', s)
        if m and len(m.group(1)) > 3:
            return m.group(1).rstrip(".")
    above = lines[block.start - 2].strip() if block.start >= 2 else ""
    m = re.match(r"^(?://|#|/\*\*?|\*)\s*(.+?)\s*(?:\*/)?$", above)
    if m and len(m.group(1)) > 3:
        return m.group(1).rstrip(".")
    return None


def _words(name: str) -> str:
    name = name.split("(")[0].split(".")[-1]
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ").split()
    return " ".join(p.lower() for p in parts)


def _imports(text: str, language: str) -> list[str]:
    if language == "python":
        mods = re.findall(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", text, re.MULTILINE)
        return [a or b for a, b in mods]
    if language == "javascript":
        pairs = re.findall(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)|from\s+['\"]([^'\"]+)['\"]", text)
        return [a or b for a, b in pairs]
    return re.findall(r"^\s*import\s+(?:static\s+)?([\w.*]+)\s*;", text, re.MULTILINE)


def _gap_title_and_text(gap: list[str], before_first: bool, language: str, label: str) -> tuple[str, str]:
    text = "\n".join(gap)
    mods = _imports(text, language)
    cls = _JAVA_CLASS.search(text)
    if language == "java" and cls:
        kind, name = cls.group(1), cls.group(2)
        decl = f"It declares the {kind} {name} and the fields (stored values) and constants that the methods below use."
        if mods:
            return (
                f"Imports and {name} {kind} declaration",
                f"This part imports {', '.join(mods[:6])}. {decl}",
            )
        return f"{name} {kind} declaration", f"This part sets up the {kind}. {decl}"
    if before_first:
        if mods:
            return (
                "Imports and setup",
                f"This part loads the libraries the code needs ({', '.join(mods[:6])}) and sets up values used "
                "later. Nothing here processes input yet.",
            )
        return (
            "Imports and setup",
            "This part sets up comments, constants and other values used later in the code.",
        )
    return (
        "Top-level code",
        f"This part runs at the top level of the {label} file: it creates shared objects, registers handlers "
        "or exports functions for other modules to use.",
    )


def build_breakdown(code: str, language: str, label: str) -> list[dict]:
    lines = code.split("\n")
    n = len(lines)
    blocks = find_blocks(code, language)
    sections: list[dict] = []

    def is_blank_or_brace(seg: list[str]) -> bool:
        return all(not s.strip() or re.fullmatch(r"[}\])\s;]*", s.strip()) for s in seg)

    cursor = 1
    for b in blocks:
        if b.start > cursor:
            gap = lines[cursor - 1 : b.start - 1]
            if is_blank_or_brace(gap) and sections:
                sections[-1]["end_line"] = b.start - 1
            elif not is_blank_or_brace(gap):
                title, text = _gap_title_and_text(gap, not sections, language, label)
                sections.append(
                    {
                        "start_line": cursor,
                        "end_line": b.start - 1,
                        "title": title,
                        "explanation": text,
                    }
                )
            elif not sections:
                b = Block(cursor, b.end, b.kind, b.name)
        doc = _doc_of(lines, b)
        body = "\n".join(lines[b.start - 1 : b.end])
        calls = _calls("\n".join(lines[b.start : b.end]), b.name)
        kind_word = {
            "handler": "request/event handler",
            "constructor": "constructor",
        }.get(b.kind, b.kind)
        sentences = [f"This part defines the {kind_word} `{b.name}`."]
        handler = re.match(r"(\w+)\.(\w+)\((.*)\)$", b.name) if b.kind == "handler" else None
        if handler and handler.group(2) in ("get", "post", "put", "patch", "delete"):
            sentences.append(f"It handles HTTP {handler.group(2).upper()} requests to {handler.group(3)}.")
        elif handler and handler.group(2) in ("addEventListener", "on"):
            sentences.append(f'It runs when the "{handler.group(3)}" event happens on {handler.group(1)}.')
        elif doc:
            sentences.append(f"According to its comment, it is meant to: {doc[0].lower() + doc[1:]}.")
        else:
            sentences.append(f"From its name, it appears to {_words(b.name)}.")
        if calls:
            sentences.append(f"It calls {', '.join(f'`{c}`' for c in calls)}.")
        if re.search(r"\b(if|for|while|try|switch)\b", body):
            flow = sorted(set(re.findall(r"\b(if|for|while|try|switch)\b", body)))
            sentences.append(f"Its control flow uses {', '.join(flow)} statements.")
        sections.append(
            {
                "start_line": b.start,
                "end_line": b.end,
                "title": f"{b.name} {'function' if b.kind == 'function' else b.kind}",
                "explanation": " ".join(sentences),
            }
        )
        cursor = b.end + 1
    if cursor <= n:
        gap = lines[cursor - 1 :]
        if is_blank_or_brace(gap) and sections:
            sections[-1]["end_line"] = n
        else:
            title, text = _gap_title_and_text(gap, not sections, language, label)
            if not sections:
                title, text = "Whole file", (
                    f"This {label} code has no separate functions; it runs its statements from top to bottom."
                )
            sections.append(
                {
                    "start_line": cursor,
                    "end_line": n,
                    "title": title,
                    "explanation": text,
                }
            )
    return sections


# ---------- heuristic pattern findings ----------
@dataclass
class Heuristic:
    key: str
    title: str
    category: str
    cwe: str | None
    severity: str
    start: int
    end: int
    evidence: str
    uncertain: bool = False


_SQL_WORDS = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", re.IGNORECASE)


def _patterns(code: str, language: str) -> list[Heuristic]:
    lines = code.split("\n")
    found: list[Heuristic] = []

    def add(key, title, category, cwe, line_no, severity=None, uncertain=False, end=None):
        sev = severity or taxonomy.base_severity(cwe) or "MEDIUM"
        found.append(
            Heuristic(
                key,
                title,
                category,
                cwe,
                taxonomy.cap_severity(sev, category),
                line_no,
                end or line_no,
                lines[line_no - 1].strip(),
                uncertain,
            )
        )

    has_close = ".close()" in code
    for no, raw in enumerate(lines, start=1):
        s = raw.strip()
        if not s or s.startswith(("#", "//", "*", "/*")):
            continue
        concat = "+" in s or "${" in s or re.search(r"\bf[\"']", s) or "%" in s or ".format(" in s
        if _SQL_WORDS.search(s) and concat and re.search(r"[\"'`]", s) and not re.search(r"\?|%s|\$\d", s):
            add("sql", "SQL query built from strings", "security", "CWE-89", no)
        if language == "python":
            if re.search(r"\bos\.(system|popen)\(|shell\s*=\s*True", s):
                add("cmd", "Shell command built from input", "security", "CWE-78", no)
            if re.search(r"\bpickle\.loads?\(|\byaml\.load\(", s):
                add("deser", "Unsafe deserialisation", "security", "CWE-502", no)
            if re.search(r"(?<![\w.])(eval|exec)\(", s):
                add("eval", "eval/exec on dynamic input", "security", "CWE-95", no)
            if re.search(r"hashlib\.(md5|sha1)\(", s):
                add("hash", "Weak hash algorithm", "security", "CWE-327", no)
            if re.match(r"except\s*:", s):
                add(
                    "bare-except",
                    "Bare except hides errors",
                    "reliability",
                    "CWE-396",
                    no,
                    "MEDIUM",
                )
            if re.search(r"=\s*open\(", s) and not s.startswith("with ") and not has_close:
                add(
                    "unclosed",
                    "File opened but never closed",
                    "reliability",
                    "CWE-404",
                    no,
                )
            if re.match(r"(async\s+)?def\s+\w+\(.*=\s*(\[\]|\{\})", s):
                add(
                    "mutable-default",
                    "Mutable default argument",
                    "reliability",
                    None,
                    no,
                    "MEDIUM",
                )
            if re.search(r"os\.path\.join\([^)]*,\s*[a-z_]\w*\s*\)", s) and "open(" in code:
                add(
                    "path",
                    "File path built from input",
                    "security",
                    "CWE-22",
                    no,
                    uncertain=True,
                )
        elif language == "javascript":
            if re.search(r"\.(innerHTML|outerHTML)\s*=\s*(?![\"'][^\"'+]*[\"']\s*;?$)", s):
                add(
                    "xss",
                    "Untrusted data written with innerHTML",
                    "security",
                    "CWE-79",
                    no,
                )
            if re.search(r"(?<![\w.])eval\(|new Function\(", s):
                add("eval", "eval on dynamic input", "security", "CWE-95", no)
            if re.search(r"(?<![\w.])(exec|execSync)\(\s*(`[^`]*\$\{|[^\"'`)]+\+|\w+\s*[,)])", s):
                add("cmd", "Shell command built from input", "security", "CWE-78", no)
            if re.search(r"\.sendFile\((?![\"'])", s) or re.search(r"readFile(Sync)?\([^)]*req\.", s):
                add(
                    "path",
                    "File path built from request data",
                    "security",
                    "CWE-22",
                    no,
                )
            if "Math.random()" in s and re.search(r"token|secret|password|key|session", code, re.IGNORECASE):
                add(
                    "random",
                    "Predictable random value used for a secret",
                    "security",
                    "CWE-338",
                    no,
                )
            if (
                re.search(r"\w+\[(\w+)\]\s*=\s*\w+\[\1\]", s)
                and re.search(r"for\s*\(\s*(const|let|var)\s+\w+\s+in\b", code)
                and "__proto__" not in code
            ):
                add(
                    "proto",
                    "Prototype pollution in object merge",
                    "security",
                    "CWE-1321",
                    no,
                )
            if re.search(r"[^=!<>]==[^=]|!=[^=]", s):
                add(
                    "loose-equality",
                    "Loose equality comparison",
                    "maintainability",
                    None,
                    no,
                    "LOW",
                )
            if (
                re.search(r"await fetch\(", s)
                and "response.ok" not in code
                and ".ok)" not in code
                and "catch" not in code
            ):
                add(
                    "fetch",
                    "Failed requests are not handled",
                    "reliability",
                    "CWE-703",
                    no,
                    "MEDIUM",
                    uncertain=True,
                )
        else:  # java
            if re.search(r"Runtime\.getRuntime\(\)\.exec\((?!\")", s):
                add(
                    "cmd",
                    "Operating-system command built from input",
                    "security",
                    "CWE-78",
                    no,
                )
            if re.search(r"getConnection\([^)]*,\s*\"[^\"]*\"\s*\)", s):
                add("secret", "Hard-coded database password", "security", "CWE-798", no)
            if ".readObject()" in s:
                add("deser", "Unsafe Java deserialisation", "security", "CWE-502", no)
            if re.search(r"new File\([^)]*\+", s):
                add("path", "File path built from input", "security", "CWE-22", no)
            if re.search(r"getInstance\(\"(MD5|SHA-?1|DES)\"", s):
                add("hash", "Weak cryptographic algorithm", "security", "CWE-327", no)
            if "DocumentBuilderFactory.newInstance()" in s and "disallow-doctype-decl" not in code:
                add(
                    "xxe",
                    "XML parser allows external entities (XXE)",
                    "security",
                    "CWE-611",
                    no,
                )
            if (
                re.search(
                    r"=\s*new (BufferedReader|FileReader|FileInputStream|FileOutputStream|FileWriter)\(",
                    s,
                )
                and not s.startswith("try")
                and not has_close
            ):
                add("unclosed", "Stream is never closed", "reliability", "CWE-404", no)
            if re.search(r"^\s*\w+\s*\+=\s*", s) and re.search(r"String\s+\w+\s*=\s*\"\"", code):
                add(
                    "string-concat-loop",
                    "String concatenation inside a loop",
                    "performance",
                    None,
                    no,
                    "MEDIUM",
                )
        if language in ("java", "javascript") and re.search(r"catch\s*(\([^)]*\))?\s*\{\s*\}", s):
            add(
                "empty-catch",
                "Empty catch block",
                "reliability",
                "CWE-390",
                no,
                "MEDIUM",
            )
    # Multi-line empty catch blocks: "catch (...) {" followed by a line with only "}".
    if language in ("java", "javascript"):
        for no in range(1, len(lines)):
            if re.search(r"catch\s*(\([^)]*\))?\s*\{\s*$", lines[no - 1]) and lines[no].strip() == "}":
                add(
                    "empty-catch",
                    "Empty catch block",
                    "reliability",
                    "CWE-390",
                    no,
                    "MEDIUM",
                    end=no + 1,
                )
    # Python nested loop over a growing list (quadratic duplicate check).
    if language == "python":
        for no, raw in enumerate(lines, start=1):
            m = re.match(r"^(\s*)for \w+ in (\w+):", raw)
            if m:
                inner = [
                    k
                    for k in range(no, min(no + 8, len(lines)))
                    if re.match(rf"^{m.group(1)}\s+for \w+ in \w+:", lines[k])
                ]
                if inner:
                    add(
                        "quadratic",
                        "Nested loop makes the check slow on large lists",
                        "performance",
                        None,
                        no,
                        "MEDIUM",
                        end=min(len(lines), inner[0] + 4),
                    )
    return found


# ---------- improved code ----------
def _comment_prefix(language: str) -> str:
    return "#" if language == "python" else "//"


@dataclass
class Rewrite:
    line: int | None  # original line (1-based) or None for added lines
    description: str
    reason: str


def _after_leading_doc(lines: list[str]) -> int:
    """Index just after a leading module docstring (Python) or comment block (JS), else 0."""
    if not lines:
        return 0
    first = lines[0].strip()
    if first.startswith(('"""', "'''")):
        quote = first[:3]
        if first.count(quote) >= 2 and len(first) > 3:
            return 1
        for k in range(1, len(lines)):
            if quote in lines[k]:
                return k + 1
        return 0
    pos = 0
    while pos < len(lines) and lines[pos].strip().startswith("//"):
        pos += 1
    return pos


def _split_concat(expr: str) -> list[tuple[str, str]]:
    """Split `"a" + b + 'c'` into [("str","a"),("expr","b"),("str","c")], respecting quotes."""
    parts: list[tuple[str, str]] = []
    buf = ""
    quote = None
    i = 0
    while i < len(expr):
        ch = expr[i]
        if quote:
            buf += ch
            if ch == "\\" and i + 1 < len(expr):
                buf += expr[i + 1]
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf += ch
        elif ch == "+":
            parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
        i += 1
    parts.append(buf.strip())
    out = []
    for p in parts:
        if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'":
            out.append(("str", p[1:-1]))
        else:
            out.append(("expr", p))
    return out


def _parameterise(rhs: str, style: str) -> tuple[str, list[str]] | None:
    parts = _split_concat(rhs.rstrip(";").strip())
    exprs = [p for kind, p in parts if kind == "expr"]
    if not exprs or not any(kind == "str" and _SQL_WORDS.search(p) for kind, p in parts):
        return None
    sql = ""
    params: list[str] = []
    for kind, p in parts:
        if kind == "str":
            sql += p
        else:
            params.append(p)
            sql += "$" + str(len(params)) if style == "dollar" else ("%s" if style == "pyformat" else "?")
    sql = re.sub(r"'(\?|%s|\$\d+)'", r"\1", sql)
    return sql, params


def improve(code: str, language: str, label: str) -> tuple[str, list[Rewrite]]:
    lines = code.split("\n")
    out = list(lines)
    rewrites: list[Rewrite] = []
    inserts: list[tuple[int, str]] = []  # (index to insert BEFORE in out, text)
    needs_import: set[str] = set()
    sql_vars: dict[str, list[str]] = {}

    py_style = "pyformat" if re.search(r"\b(psycopg2?|pymysql|MySQLdb|mysql\.connector)\b", code) else "qmark"
    js_style = "dollar" if re.search(r"require\(['\"]pg['\"]\)|\bpool\.query\b|new Pool\(", code) else "qmark"

    for idx, line in enumerate(lines):
        no = idx + 1
        new = line
        if language == "python":
            m = re.match(r"^(\s*)(\w+)\s*=\s*(.+)$", line)
            if m and _SQL_WORDS.search(line) and "+" in line:
                res = _parameterise(m.group(3), py_style)
                if res:
                    sql, params = res
                    sql_vars[m.group(2)] = params
                    new = f'{m.group(1)}{m.group(2)} = "{sql}"'
                    rewrites.append(
                        Rewrite(
                            no,
                            "Replaced the string-built SQL text with placeholders.",
                            "The original joined user input into the SQL text, so input could "
                            "change the query (SQL injection); placeholders send the values "
                            "separately so they are always treated as data.",
                        )
                    )
            m2 = re.match(r"^(\s*)(.*\b\w+\.execute\()(\w+)\)(.*)$", new)
            if m2 and m2.group(3) in sql_vars:
                params = sql_vars[m2.group(3)]
                tup = "(" + ", ".join(params) + ("," if len(params) == 1 else "") + ")"
                new = f"{m2.group(1)}{m2.group(2)}{m2.group(3)}, {tup}){m2.group(4)}"
                rewrites.append(
                    Rewrite(
                        no,
                        "Passed the values to execute() as query parameters.",
                        "The database driver now inserts the values safely instead of the code "
                        "pasting them into the SQL text.",
                    )
                )
            if re.search(r"hashlib\.(md5|sha1)\(", new):
                new = re.sub(r"hashlib\.(md5|sha1)\(", "hashlib.sha256(", new)
                rewrites.append(
                    Rewrite(
                        no,
                        "Replaced MD5/SHA-1 with SHA-256.",
                        "MD5 and SHA-1 are broken and very fast to crack; SHA-256 is stronger. For "
                        "passwords a slow salted hash (bcrypt, scrypt or Argon2) is better still.",
                    )
                )
            if "yaml.load(" in new:
                new = new.replace("yaml.load(", "yaml.safe_load(")
                rewrites.append(
                    Rewrite(
                        no,
                        "Used yaml.safe_load instead of yaml.load.",
                        "safe_load only builds plain data, so a crafted file cannot create "
                        "arbitrary Python objects.",
                    )
                )
            if re.match(r"^\s*except\s*:\s*$", new):
                new = re.sub(r"except\s*:", "except Exception:", new)
                rewrites.append(
                    Rewrite(
                        no,
                        "Changed the bare except to except Exception.",
                        "A bare except also catches KeyboardInterrupt and SystemExit and hides "
                        "programming mistakes; catching Exception is narrower.",
                    )
                )
            if re.search(r"(?<![\w.])eval\(", new):
                new = re.sub(r"(?<![\w.])eval\(", "ast.literal_eval(", new)
                needs_import.add("ast")
                rewrites.append(
                    Rewrite(
                        no,
                        "Replaced eval with ast.literal_eval.",
                        "eval runs any Python code it is given; ast.literal_eval only accepts "
                        "literal values, so injected code cannot run. (Arithmetic needs a small "
                        "expression parser instead.)",
                    )
                )
            m3 = re.match(r"^(\s*)(\w+)\s*=\s*([\"'])\[REDACTED_\w+\]\3\s*$", new)
            if m3:
                new = f'{m3.group(1)}{m3.group(2)} = os.environ["{m3.group(2)}"]'
                needs_import.add("os")
                rewrites.append(
                    Rewrite(
                        no,
                        f"Read {m3.group(2)} from an environment variable.",
                        "The secret was written in the source code, where anyone with the code can "
                        "see it; an environment variable keeps it out of the code.",
                    )
                )
            m4 = re.match(r"^(\s*)(async\s+)?def\s+\w+\((.*)\):\s*$", new)
            if m4 and re.search(r"(\w+)\s*=\s*(\[\]|\{\})", m4.group(3)):
                arg, empty = re.search(r"(\w+)\s*=\s*(\[\]|\{\})", m4.group(3)).groups()
                new = new.replace(f"{arg}={empty}", f"{arg}=None").replace(
                    f"{arg} = {empty}", f"{arg} = None"
                )
                body_indent = m4.group(1) + "    "
                insert_at = idx + 1
                if insert_at < len(lines) and lines[insert_at].strip().startswith(('"""', "'''")):
                    q = lines[insert_at].strip()[:3]
                    j = insert_at
                    if not (lines[j].strip().count(q) >= 2 and len(lines[j].strip()) > 3):
                        j += 1
                        while j < len(lines) and q not in lines[j]:
                            j += 1
                    insert_at = j + 1
                inserts.append(
                    (
                        insert_at,
                        f"{body_indent}if {arg} is None:\n{body_indent}    {arg} = {empty}",
                    )
                )
                rewrites.append(
                    Rewrite(
                        no,
                        f"Changed the default of {arg} to None and create a new value inside.",
                        "A mutable default is created once and shared by every call, so data "
                        "leaks between calls; creating it inside the function avoids that.",
                    )
                )
        elif language == "javascript":
            if re.search(r"\.innerHTML\s*=", new):
                new = new.replace(".innerHTML", ".textContent", 1)
                rewrites.append(
                    Rewrite(
                        no,
                        "Used textContent instead of innerHTML.",
                        "innerHTML turns the text into HTML, so a comment containing <script> or "
                        "an onerror attribute would run; textContent shows it as plain text.",
                    )
                )
            m = re.match(r"^(\s*)(const|let|var)\s+(\w+)\s*=\s*(.+?);?\s*$", line)
            if m and _SQL_WORDS.search(line) and "+" in line:
                res = _parameterise(m.group(4), js_style)
                if res:
                    sql, params = res
                    sql_vars[m.group(3)] = params
                    new = f'{m.group(1)}{m.group(2)} {m.group(3)} = "{sql}";'
                    rewrites.append(
                        Rewrite(
                            no,
                            "Replaced the string-built SQL text with placeholders.",
                            "Joining request values into SQL lets an attacker change the query; "
                            "placeholders keep the values separate from the SQL.",
                        )
                    )
            m2 = re.match(r"^(.*\.query\()(\w+)\)(.*)$", new)
            if m2 and m2.group(2) in sql_vars:
                new = f"{m2.group(1)}{m2.group(2)}, [{', '.join(sql_vars[m2.group(2)])}]){m2.group(3)}"
                rewrites.append(
                    Rewrite(
                        no,
                        "Passed the values to query() as parameters.",
                        "The database driver now escapes the values instead of the code pasting "
                        "them into the SQL text.",
                    )
                )
            if re.search(r"(?<![\w.])eval\(", new):
                new = re.sub(r"(?<![\w.])eval\(", "Number(", new)
                rewrites.append(
                    Rewrite(
                        no,
                        "Replaced eval with Number.",
                        "eval runs any JavaScript it receives; Number only converts text to a "
                        "number. Use a small expression parser if formulas must be supported.",
                    )
                )
            if "Math.random()" in new and re.search(r"Math\.floor\(Math\.random\(\)\s*\*\s*([\w.]+)\)", new):
                new = re.sub(
                    r"Math\.floor\(Math\.random\(\)\s*\*\s*([\w.]+)\)",
                    r"crypto.randomInt(\1)",
                    new,
                )
                needs_import.add("crypto")
                rewrites.append(
                    Rewrite(
                        no,
                        "Used crypto.randomInt instead of Math.random.",
                        "Math.random is predictable, so tokens could be guessed; crypto.randomInt "
                        "uses a cryptographically secure generator.",
                    )
                )
            if re.search(r"[^=!<>]==[^=]|!=[^=]", new) and not re.search(r"[\"'`].*==.*[\"'`]", new):
                new = re.sub(r"(?<![=!<>])==(?!=)", "===", new)
                new = re.sub(r"!=(?!=)", "!==", new)
                rewrites.append(
                    Rewrite(
                        no,
                        "Used strict equality (===).",
                        '== converts values before comparing (for example 0 == "" is true); === '
                        "compares without conversion, which avoids surprising results.",
                    )
                )
            m3 = re.match(
                r"^(\s*)(const|let|var)\s+(\w+)\s*=\s*([\"'])\[REDACTED_\w+\]\4;?\s*$",
                new,
            )
            if m3:
                new = f"{m3.group(1)}{m3.group(2)} {m3.group(3)} = process.env.{m3.group(3)};"
                rewrites.append(
                    Rewrite(
                        no,
                        f"Read {m3.group(3)} from an environment variable.",
                        "The secret was written in the source code; reading it from the "
                        "environment keeps it out of the code and lets it be rotated.",
                    )
                )
        else:  # java
            if re.search(r"getInstance\(\"(MD5|SHA-?1)\"\)", new):
                new = re.sub(r"getInstance\(\"(MD5|SHA-?1)\"\)", 'getInstance("SHA-256")', new)
                rewrites.append(
                    Rewrite(
                        no,
                        "Replaced MD5/SHA-1 with SHA-256.",
                        "MD5 and SHA-1 are broken; SHA-256 is stronger. For passwords a slow salted "
                        "hash such as bcrypt or PBKDF2 is better still.",
                    )
                )
            m = re.search(r"(getConnection\([^)]*,\s*)\"([^\"]*)\"(\s*\))", new)
            if m:
                new = new.replace(m.group(0), f'{m.group(1)}System.getenv("DB_PASSWORD"){m.group(3)}')
                rewrites.append(
                    Rewrite(
                        no,
                        "Read the database password from the DB_PASSWORD environment variable.",
                        "A password in the source code is visible to anyone with the code and "
                        "cannot be changed without a new release.",
                    )
                )
            m2 = re.match(
                r"^(\s*)(?:DocumentBuilderFactory\s+)?(\w+)\s*=\s*DocumentBuilderFactory\.newInstance\(\);",
                new,
            )
            if m2 and "disallow-doctype-decl" not in code:
                inserts.append(
                    (
                        idx + 1,
                        f"{m2.group(1)}{m2.group(2)}.setFeature("
                        f'"http://apache.org/xml/features/disallow-doctype-decl", true);',
                    )
                )
                rewrites.append(
                    Rewrite(
                        no,
                        "Disabled DOCTYPE declarations on the XML parser.",
                        "Without this, a crafted XML file can use external entities to read local "
                        "files (XXE); disabling DOCTYPE blocks that.",
                    )
                )
            m3 = re.match(r"^(\s*)\}\s*catch\s*\((\w+(?:\s*\|\s*\w+)*)\s+(\w+)\)\s*\{\s*$", new)
            if m3 and idx + 1 < len(lines) and lines[idx + 1].strip() == "}":
                inserts.append(
                    (
                        idx + 1,
                        f"{m3.group(1)}    throw new IllegalStateException("
                        f'"Operation failed", {m3.group(3)});',
                    )
                )
                rewrites.append(
                    Rewrite(
                        no,
                        "The empty catch block now reports the error.",
                        "An empty catch hides failures, so callers think the operation worked; "
                        "re-throwing makes the failure visible.",
                    )
                )
            m4 = re.match(
                r"^(\s*)((?:private\s+|public\s+)?(?:static\s+)?(?:final\s+)?String\s+(\w+))\s*=\s*\"\[REDACTED_\w+\]\";",
                new,
            )
            if m4:
                new = f'{m4.group(1)}{m4.group(2)} = System.getenv("{m4.group(3)}");'
                rewrites.append(
                    Rewrite(
                        no,
                        f"Read {m4.group(3)} from an environment variable.",
                        "The secret was hard-coded in the source; the environment keeps it out of "
                        "the code.",
                    )
                )
        out[idx] = new

    for at, text in sorted(inserts, reverse=True):
        out.insert(at, text)
    header: list[str] = []
    if language == "python":
        for mod in sorted(needs_import):
            if not re.search(rf"^\s*import {mod}\b", code, re.MULTILINE):
                header.append(f"import {mod}")
                rewrites.append(
                    Rewrite(
                        None,
                        f"Added `import {mod}` (standard library).",
                        f"The fix above needs the standard-library module {mod}.",
                    )
                )
    elif language == "javascript" and "crypto" in needs_import and 'require("crypto")' not in code:
        header.append('const crypto = require("crypto");')
        rewrites.append(
            Rewrite(
                None,
                "Added the Node.js crypto module.",
                "crypto.randomInt is part of Node.js's built-in crypto module.",
            )
        )
    if header:
        pos = _after_leading_doc(out)
        if pos > 0 and out[pos - 1].strip():
            header = [
                "",
                *header,
            ]  # keep a blank line between the module description and the imports
        out[pos:pos] = header
    improved = "\n".join(out)
    if not rewrites:
        improved = f"{_comment_prefix(language)} Reviewed: see findings for recommended changes\n{code}"
        rewrites.append(
            Rewrite(
                None,
                "Added a review note at the top of the file.",
                "No automatic fix was available for the reported problems; the note points to the "
                "findings, which explain how to fix each one.",
            )
        )
    return improved, rewrites


# ---------- building the replies ----------
def _group_static(refs: list[StaticRef]) -> list[list[StaticRef]]:
    groups: list[list[StaticRef]] = []
    for r in refs:
        for g in groups:
            g0 = g[0]
            near = r.start - 2 <= max(x.end for x in g) and min(x.start for x in g) - 2 <= r.end
            same = (r.cwe and g0.cwe and taxonomy.cwe_match(r.cwe, g0.cwe)) or (
                not r.cwe and not g0.cwe and r.rule == g0.rule
            )
            if near and same:
                g.append(r)
                break
        else:
            groups.append([r])
    return groups


def _category_for_static(ref: StaticRef) -> str:
    if ref.cwe:
        return taxonomy.category_for_cwe(ref.cwe)
    if ref.tool == "eslint":
        return taxonomy.eslint_category(ref.rule)
    rule = ref.rule.lower()
    if any(
        k in rule
        for k in (
            "performance",
            "stringbuffer",
            "instantiating",
            "concat",
            "loop",
            "inefficient",
        )
    ):
        return "performance"
    if any(
        k in rule
        for k in (
            "mutable",
            "except",
            "error",
            "null",
            "close",
            "unused-result",
            "equal",
        )
    ):
        return "reliability"
    return "maintainability"


def _finding_from_group(group: list[StaticRef], lines: list[str]) -> dict:
    ref = next((r for r in group if r.cwe), group[0])
    cwe = taxonomy.normalise_cwe(ref.cwe)
    category = _category_for_static(ref)
    start = min(r.start for r in group)
    end = max(r.end for r in group)
    key = "mutable-default" if "mutable" in ref.rule else ("loose-equality" if ref.rule == "eqeqeq" else None)
    title = (
        taxonomy.cwe_name(cwe)
        if cwe and cwe in taxonomy.CWE_TABLE
        else (ref.message.split(".")[0][:80] or ref.rule)
    )
    title = title[0].upper() + title[1:]
    consequence = CONSEQUENCES.get(
        taxonomy.cwe_family(cwe) or "", "the code may behave incorrectly or unsafely"
    )
    severity = (
        taxonomy.base_severity(cwe)
        if (cwe and category == "security")
        else ("MEDIUM" if category in ("reliability", "performance") else "LOW")
    )
    return {
        "title": title,
        "category": category,
        "start_line": start,
        "end_line": end,
        "description": f"Static analysis ({', '.join(dict.fromkeys(r.tool for r in group))}) reported: "
        f"{ref.message.rstrip('.')}. If this is real, {consequence}.",
        "evidence": lines[start - 1].strip() if 0 < start <= len(lines) else "",
        "recommendation": recommendation_for(cwe, key),
        "severity_suggested": taxonomy.cap_severity(severity or "MEDIUM", category),
        "cwe_id": cwe,
        "model_uncertain": False,
        "related_static_ids": [r.id for r in group],
    }


def _finding_from_heuristic(h: Heuristic) -> dict:
    consequence = CONSEQUENCES.get(
        taxonomy.cwe_family(h.cwe) or "", "the code may behave incorrectly or slowly"
    )
    return {
        "title": h.title,
        "category": h.category,
        "start_line": h.start,
        "end_line": h.end,
        "description": f"This pattern is a known source of problems: {consequence}.",
        "evidence": h.evidence
        + (" (pattern match only; the context may make it safe)" if h.uncertain else ""),
        "recommendation": recommendation_for(h.cwe, h.key),
        "severity_suggested": h.severity,
        "cwe_id": h.cwe,
        "model_uncertain": h.uncertain,
        "related_static_ids": [],
    }


def _overlaps(a1: int, a2: int, b1: int, b2: int, tol: int = 2) -> bool:
    return a1 - tol <= b2 and b1 - tol <= a2


def mock_findings(code: str, language: str, refs: list[StaticRef]) -> list[dict]:
    lines = code.split("\n")
    findings = [_finding_from_group(g, lines) for g in _group_static(refs)]
    for h in _patterns(code, language):
        clash = any(
            _overlaps(h.start, h.end, f["start_line"], f["end_line"])
            and (
                taxonomy.cwe_match(h.cwe, f["cwe_id"])
                or (h.category == f["category"] and not (h.cwe and f["cwe_id"]))
            )
            for f in findings
        )
        if not clash:
            findings.append(_finding_from_heuristic(h))
    findings.sort(key=lambda f: (f["start_line"], f["title"]))
    return findings


def purpose_summary(code: str, language: str, label: str) -> str:
    blocks = find_blocks(code, language)
    lines = code.split("\n")
    names = [b.name for b in blocks]
    if names:
        listed = ", ".join(names[:6]) + (f" and {len(names) - 6} more" if len(names) > 6 else "")
        first_doc = _doc_of(lines, blocks[0])
        action = (first_doc[0].lower() + first_doc[1:]) if first_doc else _words(blocks[0].name)
        return (
            f"This {label} code defines {len(names)} function(s)/class(es): {listed}. It mainly helps to {action}. "
            "(Mock explanation — set LLM_PROVIDER to use a real model.)"
        )
    return (
        f"This {label} code has no named functions; it performs operations on its inputs from top to bottom. "
        "(Mock explanation — set LLM_PROVIDER to use a real model.)"
    )


def build_explanation(code: str, language: str, label: str, refs: list[StaticRef]) -> dict:
    findings = mock_findings(code, language, refs)
    improved, rewrites = improve(code, language, label)
    changes = []
    for i, rw in enumerate(rewrites, start=1):
        related = []
        if rw.line is not None:
            related = [
                k
                for k, f in enumerate(findings, start=1)
                if _overlaps(rw.line, rw.line, f["start_line"], f["end_line"])
            ]
        changes.append(
            {
                "number": i,
                "description": rw.description,
                "reason": rw.reason,
                "related_findings": related,
                "original_lines": [rw.line, rw.line] if rw.line else None,
            }
        )
    return {
        "purpose_summary": purpose_summary(code, language, label),
        "breakdown": build_breakdown(code, language, label),
        "findings": findings,
        "static_assessment": [
            {
                "static_id": r.id,
                "verdict": "agree",
                "reason": "The flagged line matches a known risky pattern.",
            }
            for r in refs
        ],
        "improved_code": improved,
        "changes": changes,
        "sensitive_domains": detect_domains(code),
        "limitations": [MOCK_LIMITATION],
    }


def build_baseline(code: str, language: str, label: str) -> str:
    findings = mock_findings(code, language, [])
    text = [purpose_summary(code, language, label), "", "Possible problems:"]
    if not findings:
        text.append("- I did not notice any obvious problems.")
    for f in findings:
        text.append(f"- Line {f['start_line']}: {f['title']}. {f['recommendation']}")
    return "\n".join(text)


# ---------- the client ----------
class _ExplainCache:
    """Remembers the findings of the main explanation so the consistency run returns the same ones."""

    def __init__(self, size: int = 256):
        self._data: OrderedDict[str, list[dict]] = OrderedDict()
        self._cond = threading.Condition()
        self._size = size

    def put(self, key: str, findings: list[dict]) -> None:
        with self._cond:
            self._data[key] = findings
            self._data.move_to_end(key)
            while len(self._data) > self._size:
                self._data.popitem(last=False)
            self._cond.notify_all()

    def get(self, key: str, timeout: float = 5.0) -> list[dict] | None:
        with self._cond:
            self._cond.wait_for(lambda: key in self._data, timeout=timeout)
            return self._data.get(key)


_CACHE = _ExplainCache()


def _language_from_label(label: str) -> str:
    return LABEL_TO_LANG.get(label.lower(), "python")


class MockClient:
    name = "mock"
    model = MOCK_MODEL

    def complete(
        self,
        system: str | None,
        user: str,
        *,
        temperature: float = 0.2,
        max_output_tokens: int = 8192,
        timeout_s: int = 90,
        json_mode: bool = True,
        response_model: type[BaseModel] | None = None,
    ) -> LLMResult:
        return LLMResult(
            text=self.respond(user),
            model=MOCK_MODEL,
            input_tokens=len(user) // 4,
            output_tokens=None,
            latency_ms=50,
        )

    def respond(self, user: str) -> str:
        baseline = _BASELINE_RE.match(user)
        if baseline:
            label = baseline.group(1)
            return build_baseline(baseline.group(2), _language_from_label(label), label)
        numbered = _NUMBERED_RE.search(user)
        lang_m = _LANG_RE.search(user)
        if not numbered or not lang_m:
            raise LLMError("api_error", "The mock provider could not understand this prompt.")
        label = lang_m.group(1)
        language = _language_from_label(label)
        code = unnumber(numbered.group(2))
        static = _STATIC_RE.search(user)
        if static is not None:
            refs = parse_static_block(static.group(1))
            data = build_explanation(code, language, label, refs)
            _CACHE.put(numbered.group(2), data["findings"])
            return json.dumps(data)
        # Consistency run (risks only): same findings as the main explanation.
        findings = _CACHE.get(numbered.group(2)) or mock_findings(code, language, [])
        keep = (
            "title",
            "category",
            "start_line",
            "end_line",
            "severity_suggested",
            "cwe_id",
            "model_uncertain",
        )
        return json.dumps({"findings": [{k: f[k] for k in keep} for f in findings]})


class FlakyMockClient(MockClient):
    """Test helper: returns invalid JSON `failures` times per call chain before answering correctly."""

    def __init__(self, failures: int = 2, kinds: tuple[str, ...] = ("explain",)):
        self.failures = failures
        self.kinds = kinds
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()
        self._local = threading.local()
        self.calls = 0

    def complete(self, system, user, **kwargs) -> LLMResult:
        with self._lock:
            self.calls += 1
        if "Your previous reply could not be used" in user:
            original = getattr(self._local, "prompt", user)
            kind = getattr(self._local, "kind", "explain")
        else:
            original = user
            kind = "explain" if "=== STATIC ANALYSIS FINDINGS" in user else "risks"
            self._local.prompt, self._local.kind = user, kind
        with self._lock:
            count = self._counts.get(kind, 0)
            self._counts[kind] = count + 1
        if kind in self.kinds and count < self.failures:
            return LLMResult(
                text="Sorry, here is my analysis: not json at all",
                model=MOCK_MODEL,
                latency_ms=50,
            )
        return super().complete(system, original, **kwargs)


class FailingMockClient(MockClient):
    """Test helper: every call fails with the given LLMError kind (default api_error)."""

    def __init__(self, kind: str = "api_error"):
        self.kind = kind
        self.calls = 0

    def complete(self, system, user, **kwargs) -> LLMResult:
        self.calls += 1
        raise LLMError(self.kind, f"Simulated {self.kind} failure")


class RecordingMockClient(MockClient):
    """Test helper: records every prompt it receives (used to prove secrets never reach the LLM)."""

    def __init__(self):
        self.prompts: list[tuple[str | None, str]] = []
        self._lock = threading.Lock()

    def complete(self, system, user, **kwargs) -> LLMResult:
        with self._lock:
            self.prompts.append((system, user))
        return super().complete(system, user, **kwargs)
