"""Create the .env file for a local Windows installation (used by SETUP-WINDOWS.bat).

Copies .env.example, generates a random JWT_SECRET and asks for the administrator account and the
Gemini API key. An existing .env is never overwritten.
"""

from __future__ import annotations

import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.example"
TARGET = ROOT / ".env"


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").replace("﻿", "").strip()
    return value or default


def ask_email() -> str:
    while True:
        value = ask("Administrator e-mail", "admin@example.com")
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            return value
        print("  That is not a valid e-mail address. Please try again.")


def ask_password() -> str:
    while True:
        value = input("Administrator password (8+ characters, at least one letter and one digit): ")
        value = value.replace("﻿", "").strip()
        if 8 <= len(value) <= 128 and re.search(r"[A-Za-z]", value) and re.search(r"\d", value):
            return value
        print("  That password is too weak. Please try again.")


def set_value(text: str, name: str, value: str) -> str:
    """Replace NAME=... (keeping any trailing # comment) or append the line."""
    pattern = re.compile(rf"^{name}=[^#\n]*?(\s*#.*)?$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(lambda m: f"{name}={value}{m.group(1) or ''}", text, count=1)
    return text + f"\n{name}={value}\n"


def main() -> int:
    if TARGET.exists():
        print(".env already exists - keeping your current settings.")
        return 0
    text = EXAMPLE.read_text(encoding="utf-8")

    print()
    print("--- Administrator account (used to log in to the Admin pages) ---")
    email = ask_email()
    password = ask_password()

    print()
    print("--- Google Gemini API key ---")
    print("Paste your free key from https://aistudio.google.com (Get API key).")
    print("Press Enter without a key to use the offline demonstration mode instead.")
    key = input("Gemini API key: ").replace("﻿", "").strip()

    text = set_value(text, "JWT_SECRET", secrets.token_urlsafe(48))
    text = set_value(text, "APP_BASE_URL", "http://localhost:8000")
    text = set_value(text, "ADMIN_EMAIL", email)
    text = set_value(text, "ADMIN_PASSWORD", password)
    text = set_value(text, "LLM_PROVIDER", "gemini" if key else "mock")
    text = set_value(text, "GEMINI_API_KEY", key)
    TARGET.write_text(text, encoding="utf-8")

    print()
    print(f"Saved settings to {TARGET}")
    print("AI mode:", "Google Gemini" if key else "offline demonstration (no API key)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
