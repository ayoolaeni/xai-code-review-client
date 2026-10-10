"""Input validation (Section 8.2, FR3)."""

from __future__ import annotations

import re

from app.errors import AppError
from app.pipeline.types import ValidatedInput

ALLOWED_EXTENSIONS = (".py", ".js", ".mjs", ".cjs", ".java")
ALLOWED_LANGUAGES = ("auto", "python", "javascript", "java")


def normalise(code: str) -> str:
    """Normalise newlines, strip a BOM and trailing whitespace at the very end."""
    if code.startswith("﻿"):
        code = code[1:]
    code = code.replace("\r\n", "\n").replace("\r", "\n")
    return code.rstrip()


def sanitise_filename(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    if len(name) > 100:
        # Keep the extension when shortening.
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 100 - len(ext) - 1] + dot + ext) if dot else name[:100]
    return name


def extension_of(filename: str | None) -> str | None:
    if not filename or "." not in filename:
        return None
    return "." + filename.rsplit(".", 1)[-1].lower()


def _non_printable_ratio(code: str) -> float:
    if not code:
        return 0.0
    bad = sum(1 for ch in code if not ch.isprintable() and ch not in "\n\t")
    return bad / len(code)


def validate(
    code: str | None,
    language: str | None,
    filename: str | None,
    max_lines: int,
    max_chars: int,
) -> ValidatedInput:
    code = normalise(code or "")
    if not code.strip():
        raise AppError(
            422,
            "EMPTY_CODE",
            "Please paste some code or upload a file before analysing.",
        )

    if "\x00" in code or _non_printable_ratio(code) > 0.10:
        raise AppError(
            422,
            "BINARY_CONTENT",
            "This looks like a binary file, not source code. Please submit a text source file.",
        )

    line_count = code.count("\n") + 1
    char_count = len(code)
    if line_count > max_lines:
        raise AppError(
            422,
            "INPUT_TOO_LONG",
            f"Your code has {line_count} lines. The limit is {max_lines} lines.",
            {"line_count": line_count, "max_lines": max_lines},
        )
    if char_count > max_chars:
        raise AppError(
            422,
            "INPUT_TOO_LONG",
            f"Your code has {char_count} characters. The limit is {max_chars} characters.",
            {"char_count": char_count, "max_chars": max_chars},
        )

    clean_name = None
    if filename:
        ext = extension_of(filename)
        if ext not in ALLOWED_EXTENSIONS:
            raise AppError(
                422,
                "UNSUPPORTED_FILE_TYPE",
                "This file type is not supported. Please upload a .py, .js, .mjs, .cjs or .java file.",
                {"extension": ext},
            )
        clean_name = sanitise_filename(filename)

    lang = (language or "auto").strip().lower()
    if lang not in ALLOWED_LANGUAGES:
        raise AppError(
            422,
            "UNSUPPORTED_LANGUAGE",
            "This language is not supported. Please choose Python, JavaScript or Java.",
            {"language": language},
        )

    return ValidatedInput(
        code=code,
        line_count=line_count,
        char_count=char_count,
        filename=clean_name,
        language=lang,
    )
