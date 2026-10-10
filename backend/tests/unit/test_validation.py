"""Input validation (Section 8.2, FR3)."""

import pytest

from app.errors import AppError
from app.pipeline.validation import normalise, sanitise_filename, validate


def _code(exc: pytest.ExceptionInfo) -> str:
    return exc.value.code


def test_empty_rejected():
    with pytest.raises(AppError) as e:
        validate("", "auto", None, 400, 40000)
    assert _code(e) == "EMPTY_CODE" and e.value.status_code == 422


def test_whitespace_rejected():
    with pytest.raises(AppError) as e:
        validate("   \n\t\n  ", "auto", None, 400, 40000)
    assert _code(e) == "EMPTY_CODE"


def test_too_many_lines():
    code = "\n".join(f"x{i} = {i}" for i in range(401))
    with pytest.raises(AppError) as e:
        validate(code, "python", None, 400, 40000)
    assert _code(e) == "INPUT_TOO_LONG"
    assert "401 lines" in e.value.message and "400" in e.value.message
    assert e.value.details == {"line_count": 401, "max_lines": 400}


def test_exactly_max_lines_ok():
    code = "\n".join(f"x{i} = {i}" for i in range(400))
    assert validate(code, "python", None, 400, 40000).line_count == 400


def test_too_many_chars():
    with pytest.raises(AppError) as e:
        validate("x = '" + "a" * 2000 + "'", "python", None, 400, 1000)
    assert _code(e) == "INPUT_TOO_LONG"


def test_binary_nul_rejected():
    with pytest.raises(AppError) as e:
        validate("abc\x00def", "auto", None, 400, 40000)
    assert _code(e) == "BINARY_CONTENT"


def test_binary_non_printable_ratio():
    with pytest.raises(AppError) as e:
        validate("ab" + "\x01\x02\x03" * 5, "auto", None, 400, 40000)
    assert _code(e) == "BINARY_CONTENT"


def test_bad_extension():
    with pytest.raises(AppError) as e:
        validate("print(1)", "auto", "script.rb", 400, 40000)
    assert _code(e) == "UNSUPPORTED_FILE_TYPE"


@pytest.mark.parametrize("name", ["a.py", "a.js", "a.mjs", "a.cjs", "A.java", "UPPER.PY"])
def test_good_extensions(name):
    assert validate("x = 1", "python", name, 400, 40000).filename == name


def test_bad_language():
    with pytest.raises(AppError) as e:
        validate("x = 1", "ruby", None, 400, 40000)
    assert _code(e) == "UNSUPPORTED_LANGUAGE"


def test_newline_normalisation_and_trailing_whitespace():
    v = validate("a = 1\r\nb = 2\r\rc = 3   \n\n\n", "python", None, 400, 40000)
    assert v.code == "a = 1\nb = 2\n\nc = 3"
    assert v.line_count == 4


def test_bom_stripped():
    assert normalise("﻿print(1)") == "print(1)"


def test_internal_blank_lines_kept():
    assert validate("a = 1\n\n\nb = 2", "python", None, 400, 40000).line_count == 4


def test_filename_sanitised():
    assert sanitise_filename("../../etc/pass wd;rm.py") == "pass_wd_rm.py"
    long_name = "a" * 200 + ".java"
    cleaned = sanitise_filename(long_name)
    assert len(cleaned) == 100 and cleaned.endswith(".java")
