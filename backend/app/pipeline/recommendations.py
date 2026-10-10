"""Built-in fix recommendations and consequences by CWE (used by the mock provider and the merge step)."""

from __future__ import annotations

from app.pipeline import taxonomy

RECOMMENDATIONS: dict[str, str] = {
    "CWE-89": "Use a parameterised query with placeholders instead of building the SQL text from strings.",
    "CWE-78": "Do not build shell commands from input. Pass a fixed program and an argument list without a shell, "
    "and validate the input against an allow-list.",
    "CWE-77": "Do not build commands from input; use an argument list and validate the input against an allow-list.",
    "CWE-94": "Never run text as code. Parse the input with a safe parser that only accepts the expected format.",
    "CWE-95": "Never pass user input to eval/exec. Use a safe parser (for example ast.literal_eval or a small "
    "expression parser) that only accepts the expected format.",
    "CWE-798": "Remove the secret from the code. Read it from an environment variable or a secrets manager, and "
    "rotate the exposed value.",
    "CWE-259": "Remove the password from the code. Read it from an environment variable or a secrets manager, and "
    "change the exposed password.",
    "CWE-321": "Remove the key from the code, load it from a secrets manager and rotate it.",
    "CWE-502": "Do not deserialise untrusted data with pickle/ObjectInputStream. Use a data-only format such as "
    "JSON and validate it.",
    "CWE-22": "Resolve the final path and check that it stays inside the allowed folder (or look the file up by an "
    "ID from an allow-list) before opening it.",
    "CWE-79": "Insert user data as text (textContent) or escape it before adding it to the page; never build HTML "
    "from untrusted strings.",
    "CWE-611": "Disable DOCTYPE declarations and external entities on the XML parser before parsing untrusted XML.",
    "CWE-918": "Only allow requests to an allow-list of hosts and block internal addresses.",
    "CWE-1321": "Skip the keys __proto__, constructor and prototype when merging, or merge into an object created "
    "with Object.create(null).",
    "CWE-327": "Use a modern algorithm. For passwords use a slow, salted password hash such as bcrypt, scrypt or "
    "Argon2; for integrity use SHA-256 or better.",
    "CWE-328": "Use a strong hash such as SHA-256; for passwords use bcrypt, scrypt or Argon2.",
    "CWE-330": "Use a cryptographically secure random generator (secrets in Python, crypto in Node.js, "
    "SecureRandom in Java).",
    "CWE-338": "Use a cryptographically secure random generator such as crypto.randomBytes or crypto.randomInt.",
    "CWE-295": "Keep TLS certificate verification enabled.",
    "CWE-404": "Close the resource when you are done, preferably with a with-statement (Python) or "
    "try-with-resources (Java).",
    "CWE-772": "Release the resource in all code paths (with-statement / try-with-resources).",
    "CWE-476": "Check for null (missing value) before using the result, or use a default value.",
    "CWE-390": "Do not silently ignore errors: log them, handle them, or let them propagate.",
    "CWE-396": "Catch only the specific exceptions you expect and handle them; let others propagate.",
    "CWE-703": "Check the response status and handle failures (try/catch or .catch) so errors are reported.",
    "CWE-209": "Log the details on the server and show the user a generic error message.",
    "CWE-1333": "Simplify the regular expression or limit the input length to avoid catastrophic backtracking.",
    "CWE-563": "Remove the unused variable or use it.",
    "CWE-561": "Remove the unreachable code.",
}
RECOMMENDATIONS_BY_KEY = {
    "mutable-default": "Use None as the default value and create a new list or dict inside the function.",
    "quadratic": "Use a set or dictionary to remember what has been seen, so each record is checked once.",
    "loose-equality": "Use strict equality (=== and !==) so values are not converted before comparing.",
    "string-concat-loop": "Build the text with a StringBuilder (or String.join) instead of += inside a loop.",
}
DEFAULT_RECOMMENDATION = "Review this line and apply the fix suggested by the tool's documentation."

CONSEQUENCES = {
    "CWE-89": "an attacker could read, change or delete data in the database",
    "CWE-78": "an attacker could run any command on the server",
    "CWE-95": "an attacker could run any code inside the application",
    "CWE-798": "anyone who sees the code can use the secret",
    "CWE-259": "anyone who sees the code can use the password",
    "CWE-502": "a crafted input could run attacker-controlled code during deserialisation",
    "CWE-22": "a crafted file name such as ../../etc/passwd could read files outside the intended folder",
    "CWE-79": "an attacker could run JavaScript in other users' browsers",
    "CWE-611": "a crafted XML file could read local files or make the server send requests",
    "CWE-1321": "an attacker could add properties to every object in the application",
    "CWE-327": "stored hashes could be cracked quickly",
    "CWE-330": "values could be guessed by an attacker",
    "CWE-338": "tokens could be predicted, allowing account takeover",
    "CWE-404": "file handles or connections can leak and eventually run out",
    "CWE-476": "the program can crash with a null-reference error",
    "CWE-390": "failures are hidden, so problems go unnoticed",
    "CWE-396": "programming mistakes are hidden together with expected errors",
    "CWE-703": "failures are not reported and the page may break silently",
}


def recommendation_for(cwe: str | None, key: str | None = None) -> str:
    if cwe and cwe in RECOMMENDATIONS:
        return RECOMMENDATIONS[cwe]
    fam = taxonomy.cwe_family(cwe)
    if fam and fam in RECOMMENDATIONS:
        return RECOMMENDATIONS[fam]
    if key and key in RECOMMENDATIONS_BY_KEY:
        return RECOMMENDATIONS_BY_KEY[key]
    return DEFAULT_RECOMMENDATION
