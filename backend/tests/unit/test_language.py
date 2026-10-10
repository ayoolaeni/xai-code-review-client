"""Language detection (Section 8.3, FR2)."""

import pytest

from app.errors import AppError
from app.pipeline.language import detect, resolve

PYTHON = [
    "import os\n\ndef list_files(path):\n    return os.listdir(path)\n",
    "from flask import Flask\napp = Flask(__name__)\n",
    "class User:\n    def __init__(self, name):\n        self.name = name\n",
    "for i in range(3):\n    if i == 1:\n        print(i)\n    elif i == 2:\n        pass\n",
    "def add(a, b):\n    # adds\n    return a + b\n\nresult = add(1, 2)\nprint(result)\n",
    "import sqlite3\nconn = sqlite3.connect('x.db')\nvalue = None\n",
]
JAVASCRIPT = [
    "const express = require('express');\nconst app = express();\n",
    "import React from 'react';\nexport default function App() { return null; }\n",
    "function add(a, b) {\n  return a + b;\n}\nconsole.log(add(1, 2));\n",
    "let items = [1, 2, 3].map((x) => x * 2);\nif (items.length === 3) { }\n",
    "document.getElementById('x').addEventListener('click', () => {});\n",
    "module.exports = { add: (a, b) => a + b };\n",
]
JAVA = [
    "public class Main {\n  public static void main(String[] args) {\n    System.out.println(1);\n  }\n}\n",
    "import java.util.List;\n\npublic class Repo {\n  private List<String> items;\n}\n",
    "private int count = 0;\npublic void increment() {\n  count++;\n}\n",
    '@Override\npublic String toString() {\n  return "x";\n}\n',
    "public class Box {\n  String name;\n  Box b = new Box();\n}\n",
]


@pytest.mark.parametrize("code", PYTHON)
def test_python_detected(code):
    assert detect(code) == "python"


@pytest.mark.parametrize("code", JAVASCRIPT)
def test_javascript_detected(code):
    assert detect(code) == "javascript"


@pytest.mark.parametrize("code", JAVA)
def test_java_detected(code):
    assert detect(code) == "java"


@pytest.mark.parametrize("code", ["hello world", "x", "SELECT * FROM users;", "<html></html>"])
def test_ambiguous_raises(code):
    with pytest.raises(AppError) as e:
        detect(code)
    assert e.value.code == "UNSUPPORTED_LANGUAGE"
    assert e.value.message == "We could not detect the language. Please choose Python, JavaScript or Java."


def test_user_choice_overrides_detection():
    r = resolve(PYTHON[0], "java", None)
    assert r.language == "java" and r.source == "user" and r.notes == []


def test_extension_precedence_over_heuristics():
    r = resolve(PYTHON[0], "auto", "thing.js")
    assert r.language == "javascript" and r.source == "auto"


def test_mismatch_note():
    r = resolve(PYTHON[0], "python", "thing.java")
    assert r.language == "python"
    assert r.notes == ["You selected Python but the file extension suggests Java."]


def test_auto_without_extension_uses_heuristics():
    r = resolve(JAVA[0], "auto", None)
    assert r.language == "java" and r.source == "auto"
