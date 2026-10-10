"""Snippet helpers: Java class wrapping with line mapping (8.5.5) and numbered listings (8.7)."""

from __future__ import annotations

import re
from dataclasses import dataclass

TYPE_DECL = re.compile(
    r"^\s*(?:(?:public|protected|private|abstract|final|static|sealed|non-sealed|strictfp)\s+)*"
    r"(?:class|interface|enum|record|@interface)\s+(\w+)",
    re.MULTILINE,
)
PUBLIC_TYPE_DECL = re.compile(
    r"^\s*public\s+(?:(?:abstract|final|static|sealed|non-sealed|strictfp)\s+)*"
    r"(?:class|interface|enum|record|@interface)\s+(\w+)",
    re.MULTILINE,
)
FILE_NAMES = {"python": "snippet.py", "javascript": "snippet.js"}


@dataclass
class PreparedSnippet:
    text: str  # the text written to disk for the tools
    filename: str
    wrapped: bool
    header_lines: int  # leading package/import lines kept outside the wrapper
    line_count: int  # number of lines in the ORIGINAL code

    def map_line(self, line: int) -> int:
        """Map a line number reported by a tool back to the original code (clamped to 1..line_count)."""
        if self.wrapped:
            # Lines after the inserted "public class Snippet {" line move up by one (line_offset = 1);
            # the wrapper line itself maps to the first body line.
            if line > self.header_lines + 1:
                line -= 1
        return max(1, min(self.line_count, line))


def prepare(code: str, language: str) -> PreparedSnippet:
    line_count = code.count("\n") + 1
    if language != "java":
        return PreparedSnippet(code, FILE_NAMES[language], False, 0, line_count)

    if TYPE_DECL.search(code):
        m = PUBLIC_TYPE_DECL.search(code)
        filename = f"{m.group(1)}.java" if m else "Snippet.java"
        return PreparedSnippet(code, filename, False, 0, line_count)

    # No top-level type: wrap the code in a class. package/import lines must stay outside the class.
    lines = code.split("\n")
    header = 0  # number of leading lines up to and including the last package/import line
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("package ", "import ")):
            header = i + 1
        elif stripped and not stripped.startswith("//"):
            break
    body = lines[header:]
    wrapped_lines = lines[:header] + ["public class Snippet {"] + ["    " + ln for ln in body] + ["}"]
    return PreparedSnippet("\n".join(wrapped_lines), "Snippet.java", True, header, line_count)


def format_numbered(code: str) -> str:
    """Prefix each line with its 1-based number, right-aligned, then ' | '."""
    lines = code.split("\n")
    width = len(str(len(lines)))
    return "\n".join(f"{i:>{width}} | {line}" for i, line in enumerate(lines, start=1))
