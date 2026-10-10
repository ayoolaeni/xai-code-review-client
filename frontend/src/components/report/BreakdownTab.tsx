import { useState } from "react";

import type { Report } from "../../api/types";
import { lineRange } from "../../utils/format";
import { EmptyState } from "../Feedback";
import { PlainText } from "../PlainText";
import { CodeViewer } from "./CodeViewer";

export function viewerCode(report: Report): string {
  return report.submission.original_code ?? report.submission.redacted_code ?? "";
}

export function BreakdownTab({ report }: { report: Report }) {
  const [active, setActive] = useState<number | null>(null);
  const sections = report.breakdown;

  if (sections.length === 0) {
    return (
      <EmptyState title="No section-by-section breakdown">
        The AI explanation was not available for this analysis, so the code could not be divided into
        explained sections. The Risks tab still lists the static analysis findings.
      </EmptyState>
    );
  }

  const highlight: [number, number] | null =
    active !== null ? [sections[active].start_line, sections[active].end_line] : null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="h-[320px] overflow-hidden rounded-md border border-line lg:sticky lg:top-4 lg:h-[600px]">
        {!report.submission.code_stored && (
          <p className="border-b border-line bg-canvas px-3 py-1 text-xs text-muted">
            Showing the version with secrets masked (the original was not stored).
          </p>
        )}
        <CodeViewer code={viewerCode(report)} language={report.submission.language} highlight={highlight} />
      </div>
      <ol className="space-y-3" aria-label="Code sections">
        {sections.map((s, i) => (
          <li key={`${s.start_line}-${i}`}>
            <button
              type="button"
              className={`w-full rounded-md border p-4 text-left transition-colors ${
                active === i ? "border-amber-500 bg-amber-50" : "border-line bg-surface hover:bg-canvas"
              }`}
              onMouseEnter={() => setActive(i)}
              onFocus={() => setActive(i)}
              onClick={() => setActive(i)}
              aria-pressed={active === i}
            >
              <span className="text-xs font-semibold uppercase tracking-wide text-muted">
                {lineRange(s.start_line, s.end_line)}
              </span>
              <span className="mt-1 block font-semibold">
                <PlainText text={s.title} />
              </span>
              <span className="mt-1 block text-sm">
                <PlainText text={s.explanation} />
              </span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
