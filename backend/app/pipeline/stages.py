"""Pipeline stage keys and labels shown to the user (Section 8.1)."""

STAGES: list[tuple[str, str]] = [
    ("validating", "Checking your code"),
    ("detecting_language", "Detecting the language"),
    ("masking_secrets", "Masking passwords and keys"),
    ("static_analysis", "Running static analysis tools"),
    ("generating_explanation", "Generating the AI explanation"),
    ("checking_consistency", "Checking the AI's answers for consistency"),
    ("merging_findings", "Combining AI and static analysis findings"),
    ("scoring", "Rating severity and confidence"),
    ("verifying_improved_code", "Checking the improved code"),
    ("saving", "Saving your report"),
    ("completed", "Done"),
]
STAGE_INDEX = {key: i + 1 for i, (key, _) in enumerate(STAGES)}
STAGE_LABEL = dict(STAGES)
STAGE_COUNT = len(STAGES)
