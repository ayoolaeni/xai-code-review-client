import type { Report } from "../../api/types";
import { ConfidenceBadge, SeverityBadge } from "../Badges";
import { PlainText } from "../PlainText";

export function SummaryCards({ report }: { report: Report }) {
  const o = report.overview;
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div className="card sm:col-span-2 lg:col-span-1">
        <h2 className="text-sm uppercase tracking-wide text-muted">Purpose</h2>
        <p className="mt-2 line-clamp-6 text-sm">
          <PlainText text={o.purpose_summary} />
        </p>
      </div>
      <div className="card">
        <h2 className="text-sm uppercase tracking-wide text-muted">Overall risk</h2>
        <div className="mt-3">
          <SeverityBadge level={o.overall_risk_level} prefix="" />
        </div>
        <p className="mt-2 text-xs text-muted">The most serious problem found ({o.counts.total} in total).</p>
      </div>
      <div className="card">
        <h2 className="text-sm uppercase tracking-wide text-muted">Overall confidence</h2>
        <div className="mt-3">
          <ConfidenceBadge level={o.overall_confidence} prefix="" />
        </div>
        <p className="mt-2 text-xs text-muted">Lowest confidence among serious findings.</p>
      </div>
      <div className="card">
        <h2 className="text-sm uppercase tracking-wide text-muted">Human review</h2>
        <p
          className={`mt-3 inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${
            o.human_review_advised
              ? "border-red-800 bg-red-50 text-red-900"
              : "border-emerald-700 text-emerald-800"
          }`}
        >
          {o.human_review_advised ? "Advised" : "Not required"}
        </p>
        <p className="mt-2 text-xs text-muted">
          {o.human_review_advised
            ? `${o.review_reasons.length} reason(s) — see the box below.`
            : "You still remain responsible for checking the code."}
        </p>
      </div>
    </div>
  );
}

export function HumanReviewBanner({ report }: { report: Report }) {
  const o = report.overview;
  if (!o.human_review_advised) {
    return (
      <div className="rounded-lg border-2 border-dashed border-line p-4 text-sm">
        <PlainText text={o.no_review_message ?? "No specific review is required."} />
      </div>
    );
  }
  return (
    <section
      aria-labelledby="review-title"
      className="rounded-lg border-2 border-dashed border-red-800 bg-red-50/60 p-4 text-sm text-ink"
    >
      <h2 id="review-title" className="text-base text-red-900">
        Human expert review is advised
      </h2>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {o.review_reasons.map((reason, i) => (
          <li key={i}>
            <PlainText text={reason} />
          </li>
        ))}
      </ul>
    </section>
  );
}
