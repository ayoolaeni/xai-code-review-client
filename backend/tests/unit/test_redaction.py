"""Secret masking (Section 8.4, FR4, NFR6)."""

import pytest

from app.pipeline.redaction import redact, synthetic_findings

CASES = [
    ("AWS_KEY", 'key = "AKIAABCDEFGHIJKLMNOP"', "AKIAABCDEFGHIJKLMNOP"),
    ("GITHUB_TOKEN", "t = ghp_" + "a" * 36, "ghp_" + "a" * 36),
    ("ANTHROPIC_KEY", "k = sk-ant-" + "b" * 30, "sk-ant-" + "b" * 30),
    ("OPENAI_KEY", "k = sk-" + "c" * 30, "sk-" + "c" * 30),
    ("GOOGLE_KEY", "g = AIza" + "d" * 35, "AIza" + "d" * 35),
    ("SLACK_TOKEN", "s = xoxb-1234567890-abcdef", "xoxb-1234567890-abcdef"),
    ("STRIPE_KEY", "s = sk_live_" + "A1b2C3d4E5f6G7h8", "sk_live_A1b2C3d4E5f6G7h8"),
    ("PAYSTACK_KEY", "p = pk_test_" + "a1b2c3d4e5" * 4, "pk_test_" + "a1b2c3d4e5" * 4),
    (
        "JWT",
        "jwt_value = eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N",
        "eyJhbGciOiJIUzI1NiJ9",
    ),
    (
        "CONNECTION_STRING",
        'url = "postgres://admin:S3cretPass@db:5432/app"',
        "S3cretPass",
    ),
    ("ASSIGNED_SECRET", 'db_password = "hunter2hunter2"', "hunter2hunter2"),
]


@pytest.mark.parametrize("kind,line,secret", CASES)
def test_each_type_masked(kind, line, secret):
    r = redact(line)
    assert secret not in r.redacted_code
    assert f"[REDACTED_{kind}]" in r.redacted_code
    assert r.by_type.get(kind, 0) >= 1


def test_connection_string_keeps_user_and_host():
    r = redact('url = "postgres://admin:S3cretPass@db:5432/app"')
    assert "postgres://admin:[REDACTED_CONNECTION_STRING]@db:5432/app" in r.redacted_code


def test_assigned_secret_keeps_name_and_quotes():
    assert redact("password = 'abc12345'").redacted_code == "password = '[REDACTED_ASSIGNED_SECRET]'"
    java = 'String password = "Pa55word!";'
    assert redact(java).redacted_code == 'String password = "[REDACTED_ASSIGNED_SECRET]";'
    js = 'const config = { "apiKey": "abcd1234efgh" };'
    assert "[REDACTED_ASSIGNED_SECRET]" in redact(js).redacted_code


def test_private_key_block_keeps_line_count():
    code = "a = 1\nkey = '''\n-----BEGIN RSA PRIVATE KEY-----\nMIIEow\nAAAA\n-----END RSA PRIVATE KEY-----\n'''\nb = 2"
    r = redact(code)
    assert r.redacted_code.count("\n") == code.count("\n")
    assert "MIIEow" not in r.redacted_code
    assert r.by_type["PRIVATE_KEY"] == 1
    assert r.redacted_code.split("\n")[3] == "[REDACTED_PRIVATE_KEY]"


@pytest.mark.parametrize(
    "line",
    [
        'password = ""',
        'password = "changeme"',
        'password = "<your password>"',
        'password = "${DB_PASSWORD}"',
        'password = os.environ["DB_PASSWORD"]',
        'password = os.environ.get("PW", "default1")',
        "const token = process.env.TOKEN || 'devtoken1';",
        'String pw = System.getenv("PW");',
        'author = "Jane Doe"',
        'token_url = "https://example.com/oauth/token"',
        'password_label = "Password"',
        'error = "password is too short"',
        'msg_password = "Please enter your password"',
    ],
)
def test_placeholders_and_env_lookups_not_masked(line):
    r = redact(line)
    assert r.count == 0, r.redacted_code
    assert r.redacted_code == line


def test_line_count_unchanged_and_counts():
    code = 'a = "x"\npassword = "secret123"\napi_key = "AKIAABCDEFGHIJKLMNOP"\n\nprint(a)'
    r = redact(code)
    assert r.redacted_code.count("\n") == code.count("\n")
    assert r.count == 2
    assert r.by_type == {"ASSIGNED_SECRET": 1, "AWS_KEY": 1}
    assert r.lines == [2, 3]


def test_synthetic_cwe798_findings():
    code = 'password = "secret123"\nx = 1\nkey = "AKIAABCDEFGHIJKLMNOP"'
    findings = synthetic_findings(redact(code))
    assert [(f.start_line, f.cwe_id, f.tool, f.rule_id) for f in findings] == [
        (1, "CWE-798", "redactor", "hardcoded-secret"),
        (3, "CWE-798", "redactor", "hardcoded-secret"),
    ]
    assert all(f.category == "security" and f.tool_severity == "CRITICAL" for f in findings)
    assert findings[0].message == "A secret value appears to be hard-coded on this line."


def test_secret_values_recorded_and_masked_in_other_text():
    r = redact('db_password = "Winter2024!Reports"\nurl = "mysql://app:Sup3rSecret@db/x"')
    assert set(r.secrets) == {"Winter2024!Reports", "Sup3rSecret"}
    from app.pipeline.redaction import mask_secrets

    msg = "Possible hardcoded password: 'Winter2024!Reports'"
    assert mask_secrets(msg, r.secrets) == "Possible hardcoded password: '[REDACTED]'"


def test_jwt_not_masked_as_assigned_twice():
    r = redact('token = "sk-' + "z" * 30 + '"')
    assert r.count == 1 and r.by_type == {"OPENAI_KEY": 1}
