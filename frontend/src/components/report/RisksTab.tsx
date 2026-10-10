import { useMemo, useState } from "react";

import type { Category, Finding, Severity, Source } from "../../api/types";
import { CATEGORY_TEXT, SEVERITY_ORDER, SOURCE_TEXT, titleCase } from "../../utils/labels";
import { EmptyState } from "../Feedback";
import { FindingCard } from "./FindingCard";

type SortBy = "severity" | "line";

export function filterAndSort(
  findings: Finding[],
  filters: { category: Category | "all"; severity: Severity | "all"; source: Source | "all" },
  sortBy: SortBy,
): Finding[] {
  const out = findings.filter(
    (f) =>
      (filters.category === "all" || f.category === filters.category) &&
      (filters.severity === "all" || f.severity === filters.severity) &&
      (filters.source === "all" || f.source === filters.source),
  );
  return [...out].sort((a, b) =>
    sortBy === "line"
      ? a.start_line - b.start_line || SEVERITY_ORDER[b.severity] - SEVERITY_ORDER[a.severity]
      : SEVERITY_ORDER[b.severity] - SEVERITY_ORDER[a.severity] || a.start_line - b.start_line,
  );
}

export function RisksTab({
  findings,
  code,
  expanded,
  onToggle,
  focusKey,
}: {
  findings: Finding[];
  code: string;
  expanded: Set<string>;
  onToggle: (key: string, open: boolean) => void;
  focusKey: string | null;
}) {
  const [category, setCategory] = useState<Category | "all">("all");
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [source, setSource] = useState<Source | "all">("all");
  const [sortBy, setSortBy] = useState<SortBy>("severity");

  const visible = useMemo(
    () => filterAndSort(findings, { category, severity, source }, sortBy),
    [findings, category, severity, source, sortBy],
  );

  if (findings.length === 0) {
    return <EmptyState title="No problems were found. This does not prove the code is safe." />;
  }

  return (
    <div className="space-y-4">
      <fieldset className="grid gap-3 rounded-lg border border-line bg-surface p-3 sm:grid-cols-4">
        <legend className="sr-only">Filter and sort findings</legend>
        <div>
          <label htmlFor="f-category" className="label">
            Category
          </label>
          <select
            id="f-category"
            className="input"
            value={category}
            onChange={(e) => setCategory(e.target.value as Category | "all")}
          >
            <option value="all">All categories</option>
            {(Object.keys(CATEGORY_TEXT) as Category[]).map((c) => (
              <option key={c} value={c}>
                {CATEGORY_TEXT[c]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="f-severity" className="label">
            Severity
          </label>
          <select
            id="f-severity"
            className="input"
            value={severity}
            onChange={(e) => setSeverity(e.target.value as Severity | "all")}
          >
            <option value="all">All severities</option>
            {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as Severity[]).map((s) => (
              <option key={s} value={s}>
                {titleCase(s)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="f-source" className="label">
            Found by
          </label>
          <select
            id="f-source"
            className="input"
            value={source}
            onChange={(e) => setSource(e.target.value as Source | "all")}
          >
            <option value="all">Any source</option>
            {(Object.keys(SOURCE_TEXT) as Source[]).map((s) => (
              <option key={s} value={s}>
                {SOURCE_TEXT[s]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="f-sort" className="label">
            Sort by
          </label>
          <select
            id="f-sort"
            className="input"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortBy)}
          >
            <option value="severity">Severity</option>
            <option value="line">Line number</option>
          </select>
        </div>
      </fieldset>

      <p className="text-sm text-muted" aria-live="polite">
        Showing {visible.length} of {findings.length} finding(s).
      </p>

      {visible.length === 0 ? (
        <EmptyState title="No findings match these filters." />
      ) : (
        <div className="space-y-3">
          {visible.map((f) => (
            <FindingCard
              key={f.key}
              finding={f}
              code={code}
              expanded={expanded.has(f.key)}
              onToggle={(open) => onToggle(f.key, open)}
              scrollIntoView={focusKey === f.key}
            />
          ))}
        </div>
      )}
    </div>
  );
}
