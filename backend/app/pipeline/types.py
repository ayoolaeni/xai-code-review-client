"""Internal dataclasses shared by the pipeline stages."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class StaticFinding:
    id: str  # "S1", "S2", … assigned after all tools finish (sorted by line)
    tool: str  # semgrep | bandit | eslint | pmd | redactor
    rule_id: str
    message: str
    start_line: int
    end_line: int
    tool_severity: str  # tool's own level, raw
    cwe_id: str | None
    owasp_category: str | None
    category: str  # security | reliability | performance | maintainability


@dataclass
class ToolRun:
    tool: str
    version: str | None
    status: str  # ok | failed | skipped | unavailable | timeout
    findings_count: int
    message: str | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RedactionResult:
    redacted_code: str
    count: int
    by_type: dict[str, int]
    lines: list[int]
    # (line, type) for every masked value — used to create synthetic CWE-798 findings.
    items: list[tuple[int, str]] = field(default_factory=list)
    # The original secret values (kept in memory only) so tool messages can be masked too.
    secrets: list[str] = field(default_factory=list)


@dataclass
class ValidatedInput:
    code: str
    line_count: int
    char_count: int
    filename: str | None
    language: str  # auto | python | javascript | java


@dataclass
class LanguageResult:
    language: str
    source: str  # user | auto
    notes: list[str] = field(default_factory=list)


@dataclass
class StaticGroup:
    """One or more static findings from different tools that describe the same problem."""

    members: list[StaticFinding]

    @property
    def ids(self) -> list[str]:
        return [m.id for m in self.members]

    @property
    def start_line(self) -> int:
        return min(m.start_line for m in self.members)

    @property
    def end_line(self) -> int:
        return max(m.end_line for m in self.members)

    @property
    def cwe_id(self) -> str | None:
        for m in self.members:
            if m.cwe_id:
                return m.cwe_id
        return None

    @property
    def category(self) -> str:
        cats = [m.category for m in self.members]
        return "security" if "security" in cats else cats[0]

    @property
    def tools(self) -> list[str]:
        out: list[str] = []
        for m in self.members:
            if m.tool not in out:
                out.append(m.tool)
        return out

    @property
    def tool_names(self) -> str:
        return ", ".join(self.tools)

    @property
    def rule_ids(self) -> str:
        out: list[str] = []
        for m in self.members:
            if m.rule_id not in out:
                out.append(m.rule_id)
        return ", ".join(out)

    @property
    def message(self) -> str:
        # Prefer a real tool message over the synthetic redactor one.
        for m in self.members:
            if m.tool != "redactor":
                return m.message
        return self.members[0].message


@dataclass
class ReportFinding:
    """A finding as it will be stored and shown (after merging)."""

    category: str
    title: str
    description: str
    evidence: str
    recommendation: str
    start_line: int
    end_line: int
    source: str  # static | llm | both
    cwe_id: str | None = None
    owasp_category: str | None = None
    static_tool: str | None = None
    static_rule_id: str | None = None
    static_tool_severity: str | None = None
    static_tool_list: list[str] = field(default_factory=list)
    ai_assessment: str | None = None
    ai_severity: str | None = None  # AI's severity_suggested
    model_uncertain: bool = False
    consistency_matched: bool | None = None  # None = consistency check not run / failed
    ai_index: int | None = None  # 1-based index in the AI findings list
    severity: str = "LOW"
    confidence: str = "MEDIUM"
    confidence_reason: str = ""
    public_key: str = ""
