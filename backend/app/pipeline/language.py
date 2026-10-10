"""Language selection and automatic detection (Section 8.3, FR2)."""

from __future__ import annotations

import re

from app.errors import AppError
from app.pipeline.types import LanguageResult
from app.pipeline.validation import extension_of

LABELS = {"python": "Python", "javascript": "JavaScript", "java": "Java"}
EXTENSION_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".java": "java",
}

M = re.MULTILINE

# (pattern, weight). Each signal counts once when present.
SIGNALS: dict[str, list[tuple[re.Pattern, int]]] = {
    "python": [
        (re.compile(r"^\s*(async\s+)?def \w+\(.*\)\s*(->\s*[^:]+)?:", M), 3),
        (
            re.compile(
                r"^\s*import \w+(\.\w+)*(\s+as\s+\w+)?(\s*,\s*\w+(\.\w+)*(\s+as\s+\w+)?)*\s*$"
                r"|^\s*from \w+(\.\w+)* import ",
                M,
            ),
            3,
        ),
        (
            re.compile(r"^\s*(if|for|while|class|def|elif|else|try|except|with)\b.*:\s*$", M),
            1,
        ),
        (re.compile(r"\bself\."), 1),
        (re.compile(r"(?<![.\w])print\("), 1),
        (re.compile(r"\b(None|True|False)\b"), 1),
        (re.compile(r"^\s*elif\b", M), 1),
    ],
    "javascript": [
        (re.compile(r"\b(const|let|var)\s+\w+\s*="), 3),
        (re.compile(r"\bfunction\s*\w*\s*\("), 1),
        (re.compile(r"=>"), 1),
        (re.compile(r"\brequire\("), 1),
        (re.compile(r"\bmodule\.exports\b"), 1),
        (re.compile(r"\bconsole\.log\b"), 1),
        (re.compile(r"===|!=="), 1),
        (re.compile(r"\b(document|window)\."), 1),
        (re.compile(r"^\s*import .* from ['\"]", M), 3),
    ],
    "java": [
        (
            re.compile(r"\b(public|private|protected)\s+(static\s+)?(class|void|[A-Z]\w*)"),
            3,
        ),
        (re.compile(r"\bSystem\.out\.print"), 1),
        (re.compile(r"^\s*import java\.", M), 3),
        (re.compile(r"\b(int|String|boolean|double|long)\s+\w+\s*[=;]"), 1),
        (re.compile(r"\bnew [A-Z]\w*\("), 1),
        (re.compile(r"@Override\b"), 1),
    ],
}

_HASH_COMMENT = re.compile(r"^\s*#", M)


def score(code: str) -> dict[str, int]:
    scores = {lang: sum(w for pat, w in signals if pat.search(code)) for lang, signals in SIGNALS.items()}
    # Python "#" comments count only when the code has no "//" comments.
    if _HASH_COMMENT.search(code) and "//" not in code:
        scores["python"] += 1
    return scores


def detect(code: str) -> str:
    scores = score(code)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (best, best_score), (_, second_score) = ranked[0], ranked[1]
    if best_score >= 2 and best_score - second_score >= 1:
        return best
    raise AppError(
        422,
        "UNSUPPORTED_LANGUAGE",
        "We could not detect the language. Please choose Python, JavaScript or Java.",
        {"scores": scores},
    )


def resolve(code: str, language: str, filename: str | None) -> LanguageResult:
    ext_lang = EXTENSION_MAP.get(extension_of(filename) or "")
    if language and language != "auto":
        notes = []
        if ext_lang and ext_lang != language:
            notes.append(
                f"You selected {LABELS[language]} but the file extension suggests {LABELS[ext_lang]}."
            )
        return LanguageResult(language=language, source="user", notes=notes)
    if ext_lang:
        return LanguageResult(language=ext_lang, source="auto")
    return LanguageResult(language=detect(code), source="auto")
