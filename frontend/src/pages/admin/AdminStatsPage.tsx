import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "../../api/client";
import { AdminNav } from "../../components/admin/AdminNav";
import { BarChart, DailyChart } from "../../components/admin/BarChart";
import { ErrorAlert } from "../../components/Feedback";
import { PageSkeleton } from "../../components/Skeleton";
import { formatDuration, percent } from "../../utils/format";
import { SOURCE_TEXT, titleCase } from "../../utils/labels";

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="card">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export function AdminStatsPage() {
  const [days, setDays] = useState(30);
  const stats = useQuery({ queryKey: ["admin-stats", days], queryFn: () => api.adminStats(days) });

  useEffect(() => {
    document.title = "Usage statistics · Administration";
  }, []);

  return (
    <div className="space-y-5">
      <h1>Administration</h1>
      <AdminNav />
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted">
          Guest data deleted by the retention job is not counted. Figures cover the last {days} days.
        </p>
        <div>
          <label htmlFor="stats-days" className="label">
            Period
          </label>
          <select
            id="stats-days"
            className="input"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </div>
      {stats.isLoading ? (
        <PageSkeleton />
      ) : stats.isError || !stats.data ? (
        <ErrorAlert message="Statistics could not be loaded." onRetry={() => stats.refetch()} />
      ) : (
        (() => {
          const s = stats.data;
          const usage = s.llm_usage_today;
          return (
            <>
              <section aria-labelledby="ai-usage-title" className="space-y-3">
                <h2 id="ai-usage-title">AI usage today (Gemini free tier)</h2>
                <div className="grid gap-3 sm:grid-cols-3">
                  <Stat
                    label="Requests today"
                    value={`${usage.requests} / ${usage.limit}`}
                    hint="Resets at midnight Pacific time"
                  />
                  <Stat label="Input tokens today" value={usage.input_tokens.toLocaleString()} />
                  <Stat label="Output tokens today" value={usage.output_tokens.toLocaleString()} />
                </div>
                <div
                  className="h-3 overflow-hidden rounded bg-canvas"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={usage.limit}
                  aria-valuenow={usage.requests}
                  aria-label="Daily AI quota used"
                >
                  <div
                    className="h-3 bg-brand"
                    style={{ width: `${Math.min(100, (usage.requests / Math.max(1, usage.limit)) * 100)}%` }}
                  />
                </div>
              </section>

              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
                <Stat label="Analyses" value={s.totals.analyses} />
                <Stat label="Completed" value={s.totals.completed} />
                <Stat label="Failed" value={s.totals.failed} />
                <Stat label="AI unavailable" value={s.totals.fallback} hint="Static-only fallback" />
                <Stat label="Registered users" value={s.totals.registered_users} />
                <Stat label="Guest analyses" value={s.totals.guest_analyses} />
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Stat label="Average time" value={formatDuration(s.avg_processing_ms)} />
                <Stat
                  label="90th percentile time"
                  value={formatDuration(s.p90_processing_ms)}
                  hint="Target ≤ 60 s"
                />
                <Stat label="Human review advised" value={percent(s.human_review_advised_rate)} />
                <Stat
                  label="Feedback"
                  value={s.feedback.avg_rating != null ? `${s.feedback.avg_rating.toFixed(1)} / 5` : "—"}
                  hint={`${s.feedback.count} rating(s), ${percent(s.feedback.helpful_rate)} found it helpful`}
                />
              </div>

              <DailyChart
                title="Analyses per day"
                data={s.per_day.map((d) => ({ date: d.date, value: d.analyses }))}
              />
              <DailyChart
                title="AI requests per day"
                data={s.llm_usage_history.map((d) => ({ date: d.date, value: d.requests }))}
              />
              <div className="grid gap-3 md:grid-cols-2">
                <BarChart
                  title="Analyses by language"
                  data={Object.entries(s.by_language).map(([label, value]) => ({
                    label: titleCase(label),
                    value,
                  }))}
                />
                <BarChart
                  title="Findings by severity"
                  data={(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map((k) => ({
                    label: titleCase(k),
                    value: s.findings_by_severity[k] ?? 0,
                  }))}
                />
                <BarChart
                  title="Findings by source"
                  data={(["both", "static", "llm"] as const).map((k) => ({
                    label: SOURCE_TEXT[k],
                    value: s.findings_by_source[k] ?? 0,
                  }))}
                />
                <BarChart
                  title="Static tool failures"
                  data={Object.entries(s.tool_failures).map(([label, value]) => ({ label, value }))}
                />
              </div>
            </>
          );
        })()
      )}
    </div>
  );
}
