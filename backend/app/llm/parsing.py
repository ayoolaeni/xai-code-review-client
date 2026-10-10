"""Extract, validate and repair LLM JSON replies (Sections 8.8, 8.9.3 and 8.10)."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.llm.client import RETRYABLE_KINDS, LLMClient, LLMError
from app.llm.output_schema import ExplanationOutput, RiskOnlyOutput
from app.llm.prompts import registry as prompts

log = logging.getLogger(__name__)

MAX_ERROR_LINES = 20
CLAMP_TOLERANCE = 2
SHORTER_REPLY = "Keep every explanation short (at most 3 sentences) so the whole reply fits."
RATE_LIMIT_DEFAULT_WAIT = 15.0
RATE_LIMIT_MAX_WAIT = 60.0
BACKOFF = (1.0, 3.0)

# Indirection so tests can skip real waiting.
sleep_fn: Callable[[float], None] = time.sleep

SemanticCheck = Callable[[BaseModel, bool], tuple[BaseModel, list[str]]]


@dataclass
class ParseOutcome:
    ok: bool
    value: BaseModel | None
    attempts: int  # LLM requests made (including repairs)
    errors: list[str]
    raw_last: str
    error_kind: str | None = None  # LLMError kind, or "invalid_output"
    model: str | None = None
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    attempt_log: list[str] = field(default_factory=list)


# ---------- text → JSON ----------
_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_-]*\s*\n(.*?)\n?```\s*$", re.DOTALL)


def strip_fences(text: str) -> str:
    text = text.strip()
    m = _FENCE_RE.match(text)
    return m.group(1).strip() if m else text


def extract_json_object(text: str) -> str | None:
    """Return the first balanced {...} block, respecting strings and escapes."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


def _pydantic_errors(e: ValidationError) -> list[str]:
    out = []
    for err in e.errors():
        path = ".".join(str(p) for p in err.get("loc", ())) or "(root)"
        out.append(f"{path}: {err.get('msg', 'invalid value')}")
    return out[:MAX_ERROR_LINES]


def parse_reply(
    text: str,
    model: type[BaseModel],
    semantic: SemanticCheck | None,
    final_attempt: bool,
) -> tuple[BaseModel | None, list[str]]:
    cleaned = strip_fences(text or "")
    if not cleaned.startswith("{"):
        extracted = extract_json_object(cleaned)
        if extracted is None:
            return None, ["The reply did not contain a JSON object."]
        cleaned = extracted
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        extracted = extract_json_object(cleaned)
        try:
            data = json.loads(extracted) if extracted else None
        except json.JSONDecodeError:
            data = None
        if data is None:
            return None, [f"The reply is not valid JSON: {e.msg} (line {e.lineno}, column {e.colno})."]
    if not isinstance(data, dict):
        return None, ["The reply must be a single JSON object."]
    try:
        value = model.model_validate(data)
    except ValidationError as e:
        return None, _pydantic_errors(e)
    if semantic is not None:
        value, errors = semantic(value, final_attempt)
        if errors:
            return None, errors[:MAX_ERROR_LINES]
    return value, []


# ---------- semantic checks (8.8) ----------
def _clamp_range(start: int, end: int, line_count: int, what: str, errors: list[str]) -> tuple[int, int]:
    if end < start:
        errors.append(f"{what}: end_line ({end}) is before start_line ({start}).")
        return start, end
    if start > line_count + CLAMP_TOLERANCE or end > line_count + CLAMP_TOLERANCE:
        errors.append(f"{what}: lines {start}-{end} are outside the code (1 to {line_count}).")
        return start, end
    return max(1, min(start, line_count)), max(1, min(end, line_count))


def explanation_checker(code: str, static_ids: list[str]) -> SemanticCheck:
    """Semantic checks for ExplanationOutput. `code` is the (redacted) code the model saw."""
    lines = code.split("\n")
    line_count = len(lines)
    non_blank = {i + 1 for i, ln in enumerate(lines) if ln.strip()}
    known_ids = set(static_ids)

    def check(value: BaseModel, final_attempt: bool) -> tuple[BaseModel, list[str]]:
        out: ExplanationOutput = value.model_copy(deep=True)  # type: ignore[assignment]
        errors: list[str] = []

        # Ranges. Lines slightly outside the code (≤2) are clamped instead of rejected.
        for i, s in enumerate(out.breakdown, start=1):
            s.start_line, s.end_line = _clamp_range(
                s.start_line, s.end_line, line_count, f"breakdown[{i}]", errors
            )
        for i, f in enumerate(out.findings, start=1):
            f.start_line, f.end_line = _clamp_range(
                f.start_line, f.end_line, line_count, f"findings[{i}]", errors
            )
            f.related_static_ids = [sid for sid in dict.fromkeys(f.related_static_ids) if sid in known_ids]
        for c in out.changes:
            if c.original_lines is not None:
                if len(c.original_lines) != 2:
                    c.original_lines = None
                else:
                    a, b = _clamp_range(
                        c.original_lines[0],
                        c.original_lines[1],
                        line_count,
                        f"changes[{c.number}].original_lines",
                        errors,
                    )
                    c.original_lines = [a, b]

        # Breakdown: no overlaps, ≥ 90% of non-blank lines covered.
        sections = sorted(out.breakdown, key=lambda s: (s.start_line, s.end_line))
        for prev, nxt in zip(sections, sections[1:], strict=False):
            if nxt.start_line <= prev.end_line:
                errors.append(
                    f"breakdown sections overlap: lines {prev.start_line}-{prev.end_line} and "
                    f"{nxt.start_line}-{nxt.end_line}."
                )
        covered = {n for s in sections for n in range(s.start_line, s.end_line + 1)}
        if non_blank:
            ratio = len(non_blank & covered) / len(non_blank)
            if ratio < 0.9:
                missing = sorted(non_blank - covered)
                errors.append(
                    f"breakdown covers only {ratio:.0%} of the non-blank lines; it must cover at least 90%. "
                    f"Uncovered lines include: {', '.join(map(str, missing[:15]))}."
                )
        out.breakdown = sections

        # Static assessments: every static ID exactly once.
        seen: dict[str, object] = {}
        for a in out.static_assessment:
            if a.static_id in known_ids and a.static_id not in seen:
                seen[a.static_id] = a
        out.static_assessment = list(seen.values())  # type: ignore[assignment]
        missing_ids = [sid for sid in static_ids if sid not in seen]
        if missing_ids and not final_attempt:
            errors.append(f"static_assessment is missing these static finding IDs: {', '.join(missing_ids)}.")
        # (On the final attempt the missing ones are filled with "not_reviewed" by the merge step.)

        # related_findings must point at existing findings (1-based).
        n_findings = len(out.findings)
        for c in out.changes:
            bad = [i for i in c.related_findings if not 1 <= i <= n_findings]
            if bad:
                if final_attempt:
                    c.related_findings = [i for i in c.related_findings if 1 <= i <= n_findings]
                else:
                    errors.append(f"changes[{c.number}].related_findings refers to missing findings: {bad}.")

        # With findings, the improved code must actually differ.
        if out.findings and out.improved_code.strip() == code.strip():
            errors.append("improved_code is identical to the original code although findings were reported.")
        return out, errors

    return check


def risks_checker(code: str) -> SemanticCheck:
    line_count = code.count("\n") + 1

    def check(value: BaseModel, final_attempt: bool) -> tuple[BaseModel, list[str]]:
        out: RiskOnlyOutput = value.model_copy(deep=True)  # type: ignore[assignment]
        errors: list[str] = []
        for i, f in enumerate(out.findings, start=1):
            f.start_line, f.end_line = _clamp_range(
                f.start_line, f.end_line, line_count, f"findings[{i}]", errors
            )
        return out, errors

    return check


# ---------- the request / repair loop (8.9.3, 8.10) ----------
def _wait_for(err: LLMError, retry_number: int) -> float:
    if err.kind == "rate_limit":
        return min(err.retry_after or RATE_LIMIT_DEFAULT_WAIT, RATE_LIMIT_MAX_WAIT)
    return BACKOFF[min(retry_number, len(BACKOFF) - 1)]


def call_with_repair(
    client: LLMClient,
    system: str | None,
    user_prompt: str,
    model: type[BaseModel],
    semantic: SemanticCheck | None,
    *,
    temperature: float,
    prompt_version: str | None = None,
    max_retries: int | None = None,
) -> ParseOutcome:
    """Call the LLM, validate the reply and repair it; retries + repairs share one budget."""
    settings = get_settings()
    version = prompt_version or settings.PROMPT_VERSION
    retries = settings.LLM_MAX_RETRIES if max_retries is None else max_retries
    allowed = 1 + max(0, retries)
    schema_text = prompts.json_schema_text(model)

    prompt = user_prompt
    calls = 0
    retry_number = 0
    blocked_count = 0
    last_text = ""
    errors: list[str] = []
    outcome = ParseOutcome(ok=False, value=None, attempts=0, errors=[], raw_last="")

    while calls < allowed:
        calls += 1
        final_attempt = calls == allowed
        try:
            result = client.complete(
                system,
                prompt,
                temperature=temperature,
                max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
                timeout_s=settings.LLM_TIMEOUT_SECONDS,
                json_mode=True,
                response_model=model,
            )
        except LLMError as e:
            outcome.attempt_log.append(f"attempt {calls}: {e.kind}")
            if e.kind == "blocked":
                blocked_count += 1
            if e.kind not in RETRYABLE_KINDS or final_attempt or blocked_count > 1:
                outcome.attempts, outcome.errors, outcome.error_kind = (
                    calls,
                    [e.message],
                    e.kind,
                )
                outcome.raw_last = last_text
                return outcome
            sleep_fn(_wait_for(e, retry_number))
            retry_number += 1
            continue

        outcome.model = result.model
        outcome.latency_ms += result.latency_ms
        outcome.tokens_in += result.input_tokens or 0
        outcome.tokens_out += result.output_tokens or 0
        if settings.LOG_PROMPTS and not settings.is_production:
            log.info("LLM reply (attempt %d): %s", calls, result.text[:4000])

        truncated = result.finish_reason == "MAX_TOKENS"
        if truncated and not result.text.strip():
            value, errors = None, ["The reply was cut off because it was too long."]
        else:
            value, errors = parse_reply(result.text, model, semantic, final_attempt)
        if value is not None:
            outcome.ok, outcome.value, outcome.attempts, outcome.errors = (
                True,
                value,
                calls,
                [],
            )
            outcome.raw_last = result.text
            return outcome
        last_text = result.text
        outcome.attempt_log.append(f"attempt {calls}: invalid output ({len(errors)} problem(s))")

        if truncated:
            # Nothing usable to repair: resend the original task and ask for a shorter answer.
            prompt = f"{user_prompt}\n\n{SHORTER_REPLY}"
        else:
            prompt = prompts.render(
                version,
                "repair_user",
                validation_errors="\n".join(f"- {e}" for e in errors[:MAX_ERROR_LINES]),
                json_schema=schema_text,
                previous_reply=last_text[:12000],
            )

    outcome.attempts, outcome.errors, outcome.error_kind = (
        calls,
        errors,
        "invalid_output",
    )
    outcome.raw_last = last_text
    return outcome
