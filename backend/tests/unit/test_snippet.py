"""Java wrapping and numbered listings."""

from app.pipeline.snippet import format_numbered, prepare


def test_numbered_listing_alignment():
    code = "\n".join(f"line{i}" for i in range(1, 11))
    out = format_numbered(code).split("\n")
    assert out[0] == " 1 | line1"
    assert out[9] == "10 | line10"


def test_python_not_wrapped():
    p = prepare("x = 1", "python")
    assert p.filename == "snippet.py" and not p.wrapped and p.map_line(1) == 1


def test_java_with_public_class_uses_class_name():
    p = prepare("public class UserDao {\n}\n", "java")
    assert p.filename == "UserDao.java" and not p.wrapped


def test_java_without_class_is_wrapped_and_lines_map_back():
    code = "int add(int a, int b) {\n    return a + b;\n}"
    p = prepare(code, "java")
    assert p.wrapped and p.filename == "Snippet.java"
    lines = p.text.split("\n")
    assert lines[0] == "public class Snippet {" and lines[-1] == "}"
    # Line 3 of the wrapped file ("    return a + b;") is line 2 of the original.
    assert lines[2].strip() == "return a + b;"
    assert p.map_line(3) == 2
    assert p.map_line(1) == 1
    assert p.map_line(99) == 3  # clamped


def test_java_imports_stay_outside_wrapper():
    code = "import java.util.List;\n\nList<String> names() {\n  return null;\n}"
    p = prepare(code, "java")
    lines = p.text.split("\n")
    assert lines[0] == "import java.util.List;"
    assert lines[1] == "public class Snippet {"
    assert lines[2].strip() == ""
    assert lines[3].strip().startswith("List<String> names()")
    assert p.map_line(4) == 3  # first body line
    assert p.map_line(1) == 1
