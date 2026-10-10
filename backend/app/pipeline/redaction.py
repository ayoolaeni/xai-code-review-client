"""Secret masking before code is sent to the external LLM (Section 8.4, FR4, NFR6).

Patterns are applied line by line so line numbers never change.
"""

from __future__ import annotations

import re
from collections import Counter

from app.pipeline.types import RedactionResult, StaticFinding

PRIVATE_KEY_BEGIN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
PRIVATE_KEY_END = re.compile(r"-----END [A-Z ]*PRIVATE KEY-----")

# Order matters: ANTHROPIC_KEY before OPENAI_KEY (both start with "sk-"),
# STRIPE/PAYSTACK before OPENAI (they also start with "sk").
TOKEN_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("AWS_KEY", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GITHUB_TOKEN", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("ANTHROPIC_KEY", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OPENAI_KEY", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("GOOGLE_KEY", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("SLACK_TOKEN", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("PAYSTACK_KEY", re.compile(r"\b(?:sk|pk)_(?:live|test)_[a-f0-9]{30,}\b")),
    ("STRIPE_KEY", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    (
        "JWT",
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    ),
]

CONNECTION_STRING = re.compile(r"([a-z][a-z0-9+.\-]*://[^:/\s\"']+:)([^@/\s\"']+)(@)", re.IGNORECASE)

ASSIGNED_SECRET = re.compile(
    r"(?i)(\b[\w.\-]*(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|private[_-]?key"
    r"|client[_-]?secret|auth)[\w.\-]*\b[\"']?\s*[:=]\s*)([\"'])([^\"'\n]{4,})(\2)"
)

# Names that contain a keyword but do not hold secrets (e.g. "author", "token_url", "passwordLabel").
_NON_SECRET_SUFFIXES = (
    "url|uri|endpoint|header|type|name|field|label|prefix|length|len|expiry|expires|ttl|scheme|policy"
    "|error|message|msg|hint|placeholder|regex|pattern|path|file|column|col|param"
)
_SUFFIX_SNAKE = re.compile(rf"(?i)[_\-.](?:{_NON_SECRET_SUFFIXES})$")
_SUFFIX_CAMEL = re.compile(rf"[a-z](?:{'|'.join(s.capitalize() for s in _NON_SECRET_SUFFIXES.split('|'))})$")


def _is_non_secret_name(name_part: str) -> bool:
    name = re.split(r"[\"'\s:=]", name_part.strip(), maxsplit=1)[0]
    last = name.rsplit(".", 1)[-1]
    return bool(
        re.search(r"(?i)author", last)
        or re.match(r"(?i)(min|max)[_A-Z]", last)
        or _SUFFIX_SNAKE.search(last)
        or _SUFFIX_CAMEL.search(last)
    )


PLACEHOLDER_VALUE = re.compile(
    r"^(?:changeme|change-me|change_me|<.*>|\$\{.*\}|\*+|x+|your[_\- ].*|todo)$", re.I
)
ENV_LOOKUP = re.compile(r"os\.environ|os\.getenv|process\.env|System\.getenv|getenv\(", re.I)

# Redaction types that represent a hard-coded secret (synthetic CWE-798 finding).
SECRET_TYPES = {
    "ASSIGNED_SECRET",
    "AWS_KEY",
    "GITHUB_TOKEN",
    "OPENAI_KEY",
    "ANTHROPIC_KEY",
    "GOOGLE_KEY",
    "SLACK_TOKEN",
    "STRIPE_KEY",
    "PAYSTACK_KEY",
    "PRIVATE_KEY",
    "CONNECTION_STRING",
}


def _token(kind: str) -> str:
    return f"[REDACTED_{kind}]"


def _is_placeholder(value: str) -> bool:
    v = value.strip()
    return not v or bool(PLACEHOLDER_VALUE.match(v)) or v.startswith("[REDACTED_")


def _redact_line(line: str, found: list[tuple[str, str]]) -> str:
    """Mask secrets in one line; append (type, original value) for each masked secret to `found`."""
    # 1. Well-known token formats.
    for kind, pattern in TOKEN_PATTERNS:

        def repl(m, kind=kind):
            found.append((kind, m.group(0)))
            return _token(kind)

        line = pattern.sub(repl, line)

    # 2. Credentials inside connection URLs (keep scheme/user and host).
    def conn_repl(m):
        if _is_placeholder(m.group(2)):
            return m.group(0)
        found.append(("CONNECTION_STRING", m.group(2)))
        return m.group(1) + _token("CONNECTION_STRING") + m.group(3)

    line = CONNECTION_STRING.sub(conn_repl, line)

    # 3. Secret-looking names assigned a string literal.
    if not ENV_LOOKUP.search(line):

        def assign_repl(m):
            value = m.group(3)
            name_part = m.group(1)
            # Sentences (two or more spaces) are messages, not secrets.
            if _is_placeholder(value) or _is_non_secret_name(name_part) or value.count(" ") >= 2:
                return m.group(0)
            found.append(("ASSIGNED_SECRET", value))
            return m.group(1) + m.group(2) + _token("ASSIGNED_SECRET") + m.group(4)

        line = ASSIGNED_SECRET.sub(assign_repl, line)
    return line


def redact(code: str) -> RedactionResult:
    lines = code.split("\n")
    out: list[str] = []
    counts: Counter[str] = Counter()
    items: list[tuple[int, str]] = []
    secrets: list[str] = []
    in_key = False
    for number, line in enumerate(lines, start=1):
        # Private key blocks: replace every line of the block, keeping the line count.
        if not in_key and PRIVATE_KEY_BEGIN.search(line):
            in_key = True
            counts["PRIVATE_KEY"] += 1
            items.append((number, "PRIVATE_KEY"))
        if in_key:
            prefix = line[: len(line) - len(line.lstrip())]
            out.append(prefix + _token("PRIVATE_KEY"))
            secrets.append(line.strip())
            if PRIVATE_KEY_END.search(line):
                in_key = False
            continue

        found: list[tuple[str, str]] = []
        new_line = _redact_line(line, found)
        for kind, value in found:
            counts[kind] += 1
            items.append((number, kind))
            secrets.append(value)
        out.append(new_line)

    return RedactionResult(
        redacted_code="\n".join(out),
        count=sum(counts.values()),
        by_type=dict(counts),
        lines=sorted({n for n, _ in items}),
        items=items,
        secrets=[s for s in dict.fromkeys(secrets) if len(s) >= 4],
    )


def mask_secrets(text: str, secrets: list[str]) -> str:
    """Hide secret values that also appear in other text, e.g. Bandit's
    "Possible hardcoded password: 'hunter2'" message, before it is sent to the LLM or stored.
    """
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text


def synthetic_findings(result: RedactionResult) -> list[StaticFinding]:
    """One CWE-798 finding per line that contained a hard-coded secret."""
    findings: list[StaticFinding] = []
    seen_lines: set[int] = set()
    for line, kind in result.items:
        if kind not in SECRET_TYPES or line in seen_lines:
            continue
        seen_lines.add(line)
        findings.append(
            StaticFinding(
                id="",
                tool="redactor",
                rule_id="hardcoded-secret",
                message="A secret value appears to be hard-coded on this line.",
                start_line=line,
                end_line=line,
                tool_severity="CRITICAL",
                cwe_id="CWE-798",
                owasp_category="A07:2021 – Identification and Authentication Failures",
                category="security",
            )
        )
    return findings
