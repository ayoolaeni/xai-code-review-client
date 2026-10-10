import type { Report } from "../../api/types";
import { domainLabel, lineRange } from "../../utils/format";
import { Chip, ConfidenceBadge, SeverityBadge, SourceBadge } from "../Badges";
import { PlainText } from "../PlainText";
import { HumanReviewBanner } from "./SummaryCards";

export function OverviewTab({
  report,
  onOpenFinding,
}: {
  report: Report;
  onOpenFinding: (key: string) => void;
}) {
  const o = report.overview;
  const top = report.findings.slice(0, 3);
  return (
    <div className="space-y-5">
      <section aria-labelledby="purpose-title" className="card">
        <h2 id="purpose-title">What this code does</h2>
        <p className="mt-2">
          <PlainText text={o.purpose_summary} />
        </p>
        {o.sensitive_domains.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <span className="text-muted">Sensitive areas handled:</span>
            {o.sensitive_domains.map((d) => (
              <Chip key={d}>{domainLabel(d)}</Chip>
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="counts-title" className="card">
        <h2 id="counts-title">Problems found by severity</h2>
        <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map((level) => (
            <div key={level} className="rounded-md border border-line p-3">
              <dt>
                <SeverityBadge level={level} prefix="" />
              </dt>
              <dd className="mt-2 text-2xl font-bold">{o.counts[level]}</dd>
            </div>
          ))}
        </dl>
      </section>

      <HumanReviewBanner report={report} />

      <section aria-labelledby="top-title" className="card">
        <h2 id="top-title">Most important findings</h2>
        {top.length === 0 ? (
          <p className="mt-2 text-sm text-muted">
            No problems were found. This does not prove the code is safe.
          </p>
        ) : (
          <ul className="mt-3 space-y-3">
            {top.map((f) => (
              <li
                key={f.key}
                className="flex flex-col gap-2 rounded-md border border-line p-3 sm:flex-row sm:items-center"
              >
                <div className="flex-1">
                  <p className="font-semibold">
                    <span className="font-mono text-muted">{f.key}</span> <PlainText text={f.title} />{" "}
                    <span className="text-sm font-normal text-muted">
                      ({lineRange(f.start_line, f.end_line)})
                    </span>
                  </p>
                  <div className="mt-1 flex flex-wrap gap-2">
                    <SeverityBadge level={f.severity} />
                    <ConfidenceBadge level={f.confidence} />
                    <SourceBadge source={f.source} />
                  </div>
                </div>
                <button type="button" className="btn-link" onClick={() => onOpenFinding(f.key)}>
                  View details →
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
