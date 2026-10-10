"""Consistency matching (8.11) and merging AI + static findings (8.12, FR11)."""

from __future__ import annotations

from dataclasses import dataclass

from app.llm.output_schema import ExplanationOutput, LLMFinding, RiskOnlyFinding
from app.pipeline import taxonomy
from app.pipeline.recommendations import recommendation_for
from app.pipeline.types import ReportFinding, StaticFinding, StaticGroup

TOLERANCE = 2


def _overlap(a: tuple[int, int], b: tuple[int, int], tol: int = TOLERANCE) -> int:
    """Size of the overlap after expanding each range by ±tol (0 = no overlap)."""
    lo = max(a[0] - tol, b[0] - tol)
    hi = min(a[1] + tol, b[1] + tol)
    return max(0, hi - lo + 1)


def _same_problem(cwe_a: str | None, cat_a: str, cwe_b: str | None, cat_b: str) -> bool:
    """Same CWE (family) when both have one, otherwise same category."""
    if cwe_a and cwe_b:
        return taxonomy.cwe_match(cwe_a, cwe_b)
    return cat_a == cat_b


# ---------- 8.11 consistency ----------
@dataclass
class ConsistencyResult:
    enabled: bool
    run_b_ok: bool | None
    matched_indexes: set[int]  # 1-based indexes of A findings matched in run B
    matched: int
    only_in_a: int
    only_in_b: int
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "run_b_ok": self.run_b_ok,
            "matched": self.matched,
            "only_in_a": self.only_in_a,
            "only_in_b": self.only_in_b,
            "reason": self.reason,
        }


def match_consistency(a: list[LLMFinding], b: list[RiskOnlyFinding]) -> ConsistencyResult:
    """Greedy one-to-one matching; prefer identical CWE, then the largest overlap."""
    candidates = []
    for i, fa in enumerate(a, start=1):
        for j, fb in enumerate(b):
            ov = _overlap((fa.start_line, fa.end_line), (fb.start_line, fb.end_line))
            if ov and _same_problem(fa.cwe_id, fa.category, fb.cwe_id, fb.category):
                same_cwe = bool(fa.cwe_id and fb.cwe_id and fa.cwe_id == fb.cwe_id)
                candidates.append((not same_cwe, -ov, i, j))
    candidates.sort()
    used_a: set[int] = set()
    used_b: set[int] = set()
    for _, _, i, j in candidates:
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
    return ConsistencyResult(
        enabled=True,
        run_b_ok=True,
        matched_indexes=used_a,
        matched=len(used_a),
        only_in_a=len(a) - len(used_a),
        only_in_b=len(b) - len(used_b),
    )


def consistency_not_run(
    enabled: bool, n_a: int, reason: str | None, run_b_ok: bool | None
) -> ConsistencyResult:
    return ConsistencyResult(enabled, run_b_ok, set(), 0, n_a if run_b_ok is False else 0, 0, reason)


# ---------- 8.12 merge ----------
def group_static(findings: list[StaticFinding]) -> list[StaticGroup]:
    """Group findings from different tools that overlap (±2 lines) and share a CWE (family)."""
    groups: list[StaticGroup] = []
    for f in sorted(findings, key=lambda x: (x.start_line, x.id)):
        target = None
        if f.cwe_id:
            for g in groups:
                if (
                    g.cwe_id
                    and taxonomy.cwe_match(g.cwe_id, f.cwe_id)
                    and _overlap((g.start_line, g.end_line), (f.start_line, f.end_line))
                ):
                    target = g
                    break
        if target is None:
            groups.append(StaticGroup([f]))
        else:
            target.members.append(f)
    return groups


def _tool_severity_level(group: StaticGroup) -> str:
    return (
        taxonomy.max_severity(*(taxonomy.tool_level(m.tool, m.tool_severity) for m in group.members))
        or "MEDIUM"
    )


def merge(
    static_findings: list[StaticFinding],
    explanation: ExplanationOutput | None,
    consistency: ConsistencyResult | None,
) -> tuple[list[ReportFinding], list[dict]]:
    """Return report findings (sorted, keyed F1, F2, …) and the changes with remapped finding keys."""
    groups = group_static(static_findings)
    id_to_group = {m.id: gi for gi, g in enumerate(groups) for m in g.members}
    ai_findings = list(explanation.findings) if explanation else []
    assessments = {a.static_id: a for a in (explanation.static_assessment if explanation else [])}

    # links[ai_index] = set of group indexes
    links: dict[int, set[int]] = {i: set() for i in range(1, len(ai_findings) + 1)}
    linked_groups: set[int] = set()
    # 1. Link by declaration.
    for i, fa in enumerate(ai_findings, start=1):
        for sid in fa.related_static_ids:
            if sid in id_to_group:
                links[i].add(id_to_group[sid])
                linked_groups.add(id_to_group[sid])
    # 2. Link by position (for groups still unlinked).
    for gi, g in enumerate(groups):
        if gi in linked_groups:
            continue
        best, best_ov = None, 0
        for i, fa in enumerate(ai_findings, start=1):
            ov = _overlap((fa.start_line, fa.end_line), (g.start_line, g.end_line))
            if ov > best_ov and _same_problem(fa.cwe_id, fa.category, g.cwe_id, g.category):
                best, best_ov = i, ov
        if best is not None:
            links[best].add(gi)
            linked_groups.add(gi)

    consistency_ran = bool(consistency and consistency.enabled and consistency.run_b_ok)
    out: list[ReportFinding] = []
    for i, fa in enumerate(ai_findings, start=1):
        matched = (i in consistency.matched_indexes) if consistency_ran else None
        linked = [groups[gi] for gi in sorted(links[i])]
        rf = ReportFinding(
            category=fa.category,
            title=fa.title,
            description=fa.description,
            evidence=fa.evidence,
            recommendation=fa.recommendation,
            start_line=fa.start_line,
            end_line=fa.end_line,
            source="llm",
            cwe_id=fa.cwe_id,
            ai_severity=fa.severity_suggested,
            model_uncertain=fa.model_uncertain,
            consistency_matched=matched,
            ai_index=i,
        )
        if linked:
            rf.source = "both"
            rf.start_line = min([fa.start_line] + [g.start_line for g in linked])
            rf.end_line = max([fa.end_line] + [g.end_line for g in linked])
            static_cwe = next((g.cwe_id for g in linked if g.cwe_id), None)
            rf.cwe_id = static_cwe or fa.cwe_id
            tools: list[str] = []
            rules: list[str] = []
            for g in linked:
                for m in g.members:
                    if m.tool not in tools:
                        tools.append(m.tool)
                    if m.rule_id not in rules:
                        rules.append(m.rule_id)
            rf.static_tool_list = tools
            rf.static_tool = ", ".join(tools)
            rf.static_rule_id = ", ".join(rules)
            rf.static_tool_severity = taxonomy.max_severity(*(_tool_severity_level(g) for g in linked))
            verdicts = {assessments[m.id].verdict for g in linked for m in g.members if m.id in assessments}
            rf.ai_assessment = "agree" if "agree" in verdicts or not verdicts else "likely_false_positive"
        out.append(rf)

    # Static groups that no AI finding describes.
    for gi, g in enumerate(groups):
        if gi in linked_groups:
            continue
        member_assessments = [assessments[m.id] for m in g.members if m.id in assessments]
        if not explanation or not member_assessments:
            ai_assessment = "not_reviewed"
            reason = None
        elif any(a.verdict == "agree" for a in member_assessments):
            ai_assessment = "agree"
            reason = next(a.reason for a in member_assessments if a.verdict == "agree")
        else:
            ai_assessment = "likely_false_positive"
            reason = member_assessments[0].reason
        cwe = g.cwe_id
        title = taxonomy.cwe_name(cwe) if cwe else g.rule_ids.split(", ")[0]
        description = g.message if not reason else f"{g.message.rstrip('.')}. AI's comment: {reason}"
        out.append(
            ReportFinding(
                category=g.category,
                title=(title[0].upper() + title[1:] if title else "Static analysis finding"),
                description=description,
                evidence="",
                recommendation=recommendation_for(cwe),
                start_line=g.start_line,
                end_line=g.end_line,
                source="static",
                cwe_id=cwe,
                static_tool=g.tool_names,
                static_tool_list=g.tools,
                static_rule_id=g.rule_ids,
                static_tool_severity=_tool_severity_level(g),
                ai_assessment=ai_assessment,
            )
        )

    # 5. OWASP from the CWE table when missing.
    for rf in out:
        rf.owasp_category = rf.owasp_category or taxonomy.owasp_for_cwe(rf.cwe_id)

    changes = [c.model_dump() for c in (explanation.changes if explanation else [])]
    return out, changes


def assign_keys(findings: list[ReportFinding], changes: list[dict]) -> tuple[list[ReportFinding], list[dict]]:
    """Sort by severity (CRITICAL→LOW) then start_line; assign F1, F2, …; remap change references."""
    findings.sort(
        key=lambda f: (
            -taxonomy.SEVERITY_RANK[f.severity],
            f.start_line,
            f.end_line,
            f.title,
        )
    )
    index_to_key: dict[int, str] = {}
    for n, f in enumerate(findings, start=1):
        f.public_key = f"F{n}"
        if f.ai_index is not None:
            index_to_key[f.ai_index] = f.public_key
    remapped = []
    for c in changes:
        keys = [index_to_key[i] for i in c.get("related_findings", []) if i in index_to_key]
        remapped.append({**c, "related_findings": list(dict.fromkeys(keys))})
    return findings, remapped
