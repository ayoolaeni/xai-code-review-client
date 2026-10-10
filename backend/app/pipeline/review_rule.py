"""Human-review rule and sensitive-domain detection (Section 8.16, FR10, Chapter Three Table 3.7)."""

from __future__ import annotations

import re

from app.pipeline.taxonomy import SEVERITY_RANK
from app.pipeline.types import ReportFinding

DOMAIN_ORDER = ["authentication", "cryptography", "payments", "personal_data"]
DOMAIN_LABELS = {
    "authentication": "authentication",
    "cryptography": "cryptography",
    "payments": "payments",
    "personal_data": "personal data",
}
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "authentication": [
        "password", "passwd", "login", "logout", "authenticate", "auth", "jwt", "session", "oauth", "token",
        "credential", "bcrypt", "hash_password", "verify_password",
    ],
    "cryptography": [
        "encrypt", "decrypt", "cipher", "crypto", "hashlib", "MessageDigest", "AES", "RSA", "hmac", "secret_key",
        "private_key", "signature",
    ],
    "payments": [
        "payment", "card_number", "cardNumber", "cvv", "iban", "stripe", "paystack", "flutterwave", "paypal",
        "checkout", "invoice", "amount", "currency", "transaction",
    ],
    "personal_data": [
        "email", "phone", "address", "date_of_birth", "dob", "ssn", "nin", "bvn", "passport", "national_id",
        "first_name", "last_name", "full_name", "gender",
    ],
}  # fmt: skip
_DOMAIN_RES = {
    domain: re.compile(r"\b(" + "|".join(re.escape(k) for k in words) + r")\b", re.IGNORECASE)
    for domain, words in DOMAIN_KEYWORDS.items()
}

NO_REVIEW_MESSAGE = (
    "No specific review is required, but you remain responsible for checking this code before using it."
)
FALLBACK_REASON = "The AI explanation could not be produced, so this report is incomplete."


def detect_domains(code: str) -> list[str]:
    """Keyword detection (case-insensitive, word boundaries) on the original code."""
    return [d for d in DOMAIN_ORDER if _DOMAIN_RES[d].search(code)]


def merge_domains(ai_domains: list[str], code: str) -> list[str]:
    found = set(ai_domains) | set(detect_domains(code))
    return [d for d in DOMAIN_ORDER if d in found]


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def review_reasons(
    findings: list[ReportFinding],
    domains: list[str],
    ai_available: bool,
    ai_unavailable_message: str | None = None,
) -> list[str]:
    """Collect every triggered condition. human_review_advised = len(reasons) > 0."""
    reasons: list[str] = []
    # 1. CRITICAL / HIGH security findings.
    for f in findings:
        if f.category == "security" and f.severity in ("CRITICAL", "HIGH"):
            where = (
                f"line {f.start_line}" if f.start_line == f.end_line else f"lines {f.start_line}–{f.end_line}"
            )
            reasons.append(
                f"This code contains a {f.severity} security issue ({f.title}, {where}). "
                "A developer with security experience should confirm the fix before the code is used."
            )
    # 2. Potentially important but uncertain findings.
    for f in findings:
        if SEVERITY_RANK[f.severity] >= SEVERITY_RANK["MEDIUM"] and f.confidence == "LOW":
            reasons.append(
                f"The system is uncertain about a potentially important issue ({f.title}). Please check it yourself."
            )
    # 3. Sensitive domains.
    if domains:
        labels = [DOMAIN_LABELS[d] for d in domains]
        reasons.append(
            f"This code handles {_join(labels)}. Mistakes in these areas have serious consequences, "
            "so a careful human review is advised."
        )
    # 4. AI explanation unavailable.
    if not ai_available:
        reasons.append(
            FALLBACK_REASON if not ai_unavailable_message else f"{FALLBACK_REASON} {ai_unavailable_message}"
        )
    return reasons
