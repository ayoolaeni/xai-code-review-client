"""Taxonomy helpers (Section 8.6)."""

import pytest

from app.pipeline import taxonomy as t


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("89", "CWE-89"),
        ("CWE89", "CWE-89"),
        ("cwe-89", "CWE-89"),
        ("CWE-89: Improper Neutralization of Special Elements", "CWE-89"),
        (89, "CWE-89"),
        (["CWE-78: OS command"], "CWE-78"),
        ("CWE-0079", "CWE-79"),
        (None, None),
        ("", None),
        ("not a cwe", None),
        (0, None),
    ],
)
def test_normalise_cwe(raw, expected):
    assert t.normalise_cwe(raw) == expected


def test_owasp_lookup_from_cwe():
    assert t.owasp_for_cwe("CWE-89") == "A03:2021 – Injection"
    assert t.owasp_for_cwe("CWE-22") == "A01:2021 – Broken Access Control"
    assert t.owasp_for_cwe("CWE-404") is None
    assert t.owasp_for_cwe("CWE-99999") is None


def test_normalise_owasp_prefers_2021():
    assert t.normalise_owasp(["A01:2017 - Injection", "A03:2021 - Injection"]) == "A03:2021 – Injection"
    assert t.normalise_owasp("A03:2021 - Injection") == "A03:2021 – Injection"
    assert t.normalise_owasp("A1:2017 - Injection") is None


def test_severity_table():
    assert t.base_severity("CWE-89") == "CRITICAL"
    assert t.base_severity("CWE-502") == "HIGH"
    assert t.base_severity("CWE-327") == "MEDIUM"
    assert t.base_severity("CWE-209") == "LOW"
    assert t.base_severity("CWE-12345") == "MEDIUM"  # unknown CWE
    assert t.base_severity(None) is None
    assert t.cwe_name("CWE-12345") == "CWE-12345"


def test_tool_maps():
    assert t.BANDIT_CWE["B608"] == "CWE-89"
    assert t.BANDIT_CWE["B105"] == "CWE-259"
    assert t.BANDIT_CWE["B602"] == "CWE-78"
    assert t.ESLINT_CWE["security/detect-child-process"] == "CWE-78"
    assert t.ESLINT_CWE["no-unused-vars"] == "CWE-563"
    assert t.PMD_CWE["CloseResource"] == "CWE-404"
    assert t.PMD_CWE["EmptyCatchBlock"] == "CWE-390"


def test_tool_levels():
    assert t.tool_level("semgrep", "ERROR") == "HIGH"
    assert t.tool_level("semgrep", "INFO") == "LOW"
    assert t.tool_level("bandit", "MEDIUM") == "MEDIUM"
    assert t.tool_level("eslint", "2") == "MEDIUM"
    assert t.tool_level("eslint", "1") == "LOW"
    assert t.tool_level("pmd", "1") == "HIGH"
    assert t.tool_level("pmd", "3") == "MEDIUM"
    assert t.tool_level("pmd", "5") == "LOW"


def test_categories():
    assert t.eslint_category("security/detect-eval-with-expression") == "security"
    assert t.eslint_category("no-eval") == "security"
    assert t.eslint_category("eqeqeq") == "reliability"
    assert t.eslint_category("no-unused-vars") == "maintainability"
    assert t.pmd_category("Security") == "security"
    assert t.pmd_category("Error Prone") == "reliability"
    assert t.pmd_category("Multithreading") == "reliability"
    assert t.pmd_category("Performance") == "performance"
    assert t.pmd_category("Best Practices") == "maintainability"
    assert t.semgrep_category("correctness", None) == "reliability"
    assert t.semgrep_category("best-practice", None) == "maintainability"
    assert t.semgrep_category(None, "CWE-89") == "security"
    assert t.semgrep_category(None, None) == "maintainability"


def test_caps_and_lowering():
    assert t.cap_severity("CRITICAL", "reliability") == "HIGH"
    assert t.cap_severity("HIGH", "performance") == "MEDIUM"
    assert t.cap_severity("HIGH", "maintainability") == "MEDIUM"
    assert t.cap_severity("CRITICAL", "security") == "CRITICAL"
    assert t.lower_one("HIGH") == "MEDIUM"
    assert t.lower_one("LOW") == "LOW"


def test_cwe_family_matching():
    assert t.cwe_match("CWE-259", "CWE-798")
    assert t.cwe_match("CWE-396", "CWE-390")
    assert not t.cwe_match("CWE-89", "CWE-78")
    assert not t.cwe_match(None, "CWE-78")


def test_cwe_info():
    assert t.cwe_info("CWE-89") == {
        "id": "CWE-89",
        "name": "SQL injection",
        "url": "https://cwe.mitre.org/data/definitions/89.html",
    }
