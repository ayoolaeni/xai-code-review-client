"""CWE / OWASP taxonomy, base severities and tool rule → CWE maps (Section 8.6)."""

from __future__ import annotations

import re

SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY_ORDER)}
CONFIDENCE_ORDER = ["LOW", "MEDIUM", "HIGH"]
CONFIDENCE_RANK = {c: i for i, c in enumerate(CONFIDENCE_ORDER)}
CATEGORIES = ("security", "reliability", "performance", "maintainability")

# ---------- 8.6.1 OWASP Top 10 (2021) ----------
OWASP_2021 = {
    "A01": "A01:2021 – Broken Access Control",
    "A02": "A02:2021 – Cryptographic Failures",
    "A03": "A03:2021 – Injection",
    "A04": "A04:2021 – Insecure Design",
    "A05": "A05:2021 – Security Misconfiguration",
    "A06": "A06:2021 – Vulnerable and Outdated Components",
    "A07": "A07:2021 – Identification and Authentication Failures",
    "A08": "A08:2021 – Software and Data Integrity Failures",
    "A09": "A09:2021 – Security Logging and Monitoring Failures",
    "A10": "A10:2021 – Server-Side Request Forgery (SSRF)",
}

# ---------- 8.6.2 CWE table: id → (short name, OWASP code or None, base severity) ----------
CWE_TABLE: dict[str, tuple[str, str | None, str]] = {
    "CWE-89": ("SQL injection", "A03", "CRITICAL"),
    "CWE-78": ("OS command injection", "A03", "CRITICAL"),
    "CWE-77": ("Command injection", "A03", "CRITICAL"),
    "CWE-94": ("Code injection", "A03", "CRITICAL"),
    "CWE-95": ("Eval injection", "A03", "CRITICAL"),
    "CWE-798": ("Hard-coded credentials", "A07", "CRITICAL"),
    "CWE-259": ("Hard-coded password", "A07", "CRITICAL"),
    "CWE-321": ("Hard-coded cryptographic key", "A02", "CRITICAL"),
    "CWE-502": ("Deserialisation of untrusted data", "A08", "HIGH"),
    "CWE-22": ("Path traversal", "A01", "HIGH"),
    "CWE-79": ("Cross-site scripting", "A03", "HIGH"),
    "CWE-611": ("XML external entities (XXE)", "A05", "HIGH"),
    "CWE-918": ("Server-side request forgery", "A10", "HIGH"),
    "CWE-862": ("Missing authorisation", "A01", "HIGH"),
    "CWE-287": ("Improper authentication", "A07", "HIGH"),
    "CWE-1321": ("Prototype pollution", "A08", "HIGH"),
    "CWE-352": ("Cross-site request forgery", "A01", "MEDIUM"),
    "CWE-327": ("Broken or risky crypto algorithm", "A02", "MEDIUM"),
    "CWE-328": ("Weak hash", "A02", "MEDIUM"),
    "CWE-329": ("Predictable IV", "A02", "MEDIUM"),
    "CWE-330": ("Insufficiently random values", "A02", "MEDIUM"),
    "CWE-338": ("Weak PRNG for security", "A02", "MEDIUM"),
    "CWE-295": ("Improper certificate validation", "A07", "HIGH"),
    "CWE-601": ("Open redirect", "A01", "MEDIUM"),
    "CWE-209": ("Error message information exposure", "A04", "LOW"),
    "CWE-532": ("Sensitive information in log", "A09", "MEDIUM"),
    "CWE-1333": ("Inefficient regular expression (ReDoS)", None, "MEDIUM"),
    "CWE-208": ("Timing discrepancy", "A02", "LOW"),
    "CWE-400": ("Uncontrolled resource consumption", None, "MEDIUM"),
    "CWE-404": ("Improper resource shutdown", None, "MEDIUM"),
    "CWE-772": ("Missing release of resource", None, "MEDIUM"),
    "CWE-476": ("NULL pointer dereference", None, "MEDIUM"),
    "CWE-390": ("Error detected without action", None, "LOW"),
    "CWE-396": ("Catching generic exception", None, "LOW"),
    "CWE-703": ("Improper handling of exceptional conditions", None, "MEDIUM"),
    "CWE-561": ("Dead code", None, "LOW"),
    "CWE-563": ("Unused variable", None, "LOW"),
    # Used by the ESLint map in 8.6.3.
    "CWE-829": ("Inclusion of functionality from untrusted source", "A08", "MEDIUM"),
    "CWE-119": ("Improper restriction of memory buffer operations", None, "MEDIUM"),
}

# CWEs that are not security weaknesses for the purpose of categorising findings.
NON_SECURITY_CWES = {
    "CWE-404": "reliability",
    "CWE-772": "reliability",
    "CWE-476": "reliability",
    "CWE-390": "reliability",
    "CWE-396": "reliability",
    "CWE-703": "reliability",
    "CWE-400": "performance",
    "CWE-561": "maintainability",
    "CWE-563": "maintainability",
}

# CWEs that describe the same weakness family; used when matching findings across tools/runs
# (e.g. Bandit reports hard-coded passwords as CWE-259, the redactor as CWE-798).
_CWE_FAMILY = {
    "CWE-259": "CWE-798",
    "CWE-321": "CWE-798",
    "CWE-94": "CWE-95",
    "CWE-77": "CWE-78",
    "CWE-328": "CWE-327",
    "CWE-338": "CWE-330",
    "CWE-396": "CWE-390",
    "CWE-772": "CWE-404",
}


# ---------- 8.6.3 Tool rule → CWE maps ----------
BANDIT_CWE = {
    **dict.fromkeys(["B105", "B106", "B107"], "CWE-259"),
    **dict.fromkeys(["B301", "B302", "B403", "B506"], "CWE-502"),
    **dict.fromkeys(["B303", "B304", "B305", "B324"], "CWE-327"),
    "B307": "CWE-95",
    "B311": "CWE-330",
    "B501": "CWE-295",
    **dict.fromkeys(["B601", "B602", "B603", "B604", "B605", "B606", "B607"], "CWE-78"),
    "B608": "CWE-89",
    **dict.fromkeys(["B110", "B112"], "CWE-390"),
}

ESLINT_CWE = {
    "no-eval": "CWE-95",
    "no-implied-eval": "CWE-95",
    "no-new-func": "CWE-95",
    "security/detect-eval-with-expression": "CWE-95",
    "security/detect-child-process": "CWE-78",
    "security/detect-non-literal-fs-filename": "CWE-22",
    "security/detect-pseudoRandomBytes": "CWE-338",
    "security/detect-unsafe-regex": "CWE-1333",
    "security/detect-non-literal-regexp": "CWE-1333",
    "security/detect-possible-timing-attacks": "CWE-208",
    "security/detect-non-literal-require": "CWE-829",
    "security/detect-buffer-noassert": "CWE-119",
    "security/detect-new-buffer": "CWE-119",
    "no-empty": "CWE-390",
    "no-unused-vars": "CWE-563",
    "no-unreachable": "CWE-561",
}
ESLINT_RELIABILITY = {
    "eqeqeq",
    "no-undef",
    "no-dupe-keys",
    "no-constant-condition",
    "no-async-promise-executor",
    "require-await",
    "no-unreachable",
}

PMD_CWE = {
    "CloseResource": "CWE-404",
    "EmptyCatchBlock": "CWE-390",
    "AvoidCatchingGenericException": "CWE-396",
    "AvoidCatchingThrowable": "CWE-396",
    "AvoidCatchingNPE": "CWE-476",
    "HardCodedCryptoKey": "CWE-321",
    "InsecureCryptoIv": "CWE-329",
    "UnusedLocalVariable": "CWE-563",
    "UnusedPrivateField": "CWE-563",
    "AvoidPrintStackTrace": "CWE-209",
}

# ---------- 8.6.4 tool severity → level ----------
SEMGREP_SEVERITY = {"ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "LOW"}
BANDIT_SEVERITY = {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW"}
CATEGORY_CAP = {
    "reliability": "HIGH",
    "performance": "MEDIUM",
    "maintainability": "MEDIUM",
}

_CWE_RE = re.compile(r"CWE[\s_-]*(\d+)", re.IGNORECASE)


def normalise_cwe(value: object) -> str | None:
    """Accept "89", "CWE89", "cwe-89", "CWE-89: Improper…" (or a list of them) → "CWE-89"."""
    if value is None:
        return None
    if isinstance(value, list | tuple):
        for item in value:
            norm = normalise_cwe(item)
            if norm:
                return norm
        return None
    if isinstance(value, int):
        return f"CWE-{value}" if value > 0 else None
    text = str(value).strip()
    if not text:
        return None
    m = _CWE_RE.search(text)
    if m:
        return f"CWE-{int(m.group(1))}"
    if text.isdigit() and int(text) > 0:
        return f"CWE-{int(text)}"
    return None


def cwe_family(cwe: str | None) -> str | None:
    return _CWE_FAMILY.get(cwe, cwe) if cwe else None


def cwe_match(a: str | None, b: str | None) -> bool:
    return bool(a and b and cwe_family(a) == cwe_family(b))


def cwe_name(cwe: str | None) -> str | None:
    if not cwe:
        return None
    return CWE_TABLE.get(cwe, (cwe, None, "MEDIUM"))[0]


def cwe_url(cwe: str) -> str:
    return f"https://cwe.mitre.org/data/definitions/{cwe.split('-')[1]}.html"


def cwe_info(cwe: str | None) -> dict | None:
    if not cwe:
        return None
    return {"id": cwe, "name": cwe_name(cwe), "url": cwe_url(cwe)}


def owasp_for_cwe(cwe: str | None) -> str | None:
    if not cwe or cwe not in CWE_TABLE:
        return None
    code = CWE_TABLE[cwe][1]
    return OWASP_2021[code] if code else None


def base_severity(cwe: str | None) -> str | None:
    """Base severity from the CWE table; unknown CWE → MEDIUM; no CWE → None."""
    if not cwe:
        return None
    return CWE_TABLE.get(cwe, (cwe, None, "MEDIUM"))[2]


def category_for_cwe(cwe: str | None, default: str = "security") -> str:
    if not cwe:
        return default
    return NON_SECURITY_CWES.get(cwe, "security")


def normalise_owasp(value: object) -> str | None:
    """Turn "A03:2021 - Injection" (or a list incl. 2017 labels) into the 2021 label of Section 8.6.1."""
    if value is None:
        return None
    items = value if isinstance(value, list | tuple) else [value]
    for item in items:
        m = re.search(r"\b(A\d{2}):2021\b", str(item))
        if m and m.group(1) in OWASP_2021:
            return OWASP_2021[m.group(1)]
    return None


def max_severity(*levels: str | None) -> str | None:
    present = [lvl for lvl in levels if lvl in SEVERITY_RANK]
    return max(present, key=SEVERITY_RANK.__getitem__) if present else None


def cap_severity(level: str, category: str) -> str:
    cap = CATEGORY_CAP.get(category)
    if cap and SEVERITY_RANK[level] > SEVERITY_RANK[cap]:
        return cap
    return level


def lower_one(level: str) -> str:
    return SEVERITY_ORDER[max(0, SEVERITY_RANK[level] - 1)]


def tool_level(tool: str, tool_severity: str) -> str:
    """Map a tool's own severity to CRITICAL/HIGH/MEDIUM/LOW (8.6.4)."""
    raw = str(tool_severity).upper()
    if tool == "semgrep":
        return SEMGREP_SEVERITY.get(raw, "MEDIUM")
    if tool == "bandit":
        return BANDIT_SEVERITY.get(raw, "MEDIUM")
    if tool == "eslint":
        return "MEDIUM" if raw == "2" else "LOW"
    if tool == "pmd":
        try:
            p = int(raw)
        except ValueError:
            return "MEDIUM"
        return "HIGH" if p <= 2 else ("MEDIUM" if p == 3 else "LOW")
    if tool == "redactor":
        return "CRITICAL"
    return raw if raw in SEVERITY_RANK else "MEDIUM"


def eslint_category(rule_id: str) -> str:
    if rule_id.startswith("security/") or rule_id in (
        "no-eval",
        "no-implied-eval",
        "no-new-func",
    ):
        return "security"
    if rule_id in ESLINT_RELIABILITY:
        return "reliability"
    return "maintainability"


def pmd_category(ruleset: str) -> str:
    r = ruleset.strip().lower()
    if r == "security":
        return "security"
    if r in ("error prone", "multithreading"):
        return "reliability"
    if r == "performance":
        return "performance"
    return "maintainability"


def semgrep_category(category: object, cwe: str | None) -> str:
    c = str(category or "").strip().lower()
    if c == "security":
        return "security"
    if c == "correctness":
        return "reliability"
    if c in ("reliability", "performance", "maintainability"):
        return c
    if c in ("best-practice", "best-practices"):
        return "maintainability"
    return "security" if cwe else "maintainability"
