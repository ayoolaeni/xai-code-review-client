import { useEffect, useState } from "react";

import type { AnalysisStatus } from "../api/types";
import { formatElapsed } from "../utils/format";
import { Spinner } from "./Feedback";

// Same order and labels as the backend (spec Section 8.1).
export const STAGES: [string, string][] = [
  ["validating", "Checking your code"],
  ["detecting_language", "Detecting the language"],
  ["masking_secrets", "Masking passwords and keys"],
  ["static_analysis", "Running static analysis tools"],
  ["generating_explanation", "Generating the AI explanation"],
  ["checking_consistency", "Checking the AI's answers for consistency"],
  ["merging_findings", "Combining AI and static analysis findings"],
  ["scoring", "Rating severity and confidence"],
  ["verifying_improved_code", "Checking the improved code"],
  ["saving", "Saving your report"],
];

export function ProgressPanel({ status }: { status: AnalysisStatus }) {
  const [now, setNow] = useState(() => Date.now());
  const [mountedAt] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const startedAt = status.started_at ? new Date(status.started_at).getTime() : mountedAt;
  const elapsed = Math.max(0, Math.round((now - startedAt) / 1000));
  const currentIndex = STAGES.findIndex(([key]) => key === status.stage);
  const queued = status.status === "queued";

  return (
    <section className="card mx-auto max-w-2xl" aria-labelledby="progress-title" aria-busy="true">
      <div className="flex items-center justify-between gap-4">
        <h1 id="progress-title" className="text-xl">
          {queued ? "Waiting to start" : "Analysing your code"}
        </h1>
        <span className="text-sm text-muted" aria-label="Elapsed time">
          ⏱ {formatElapsed(elapsed)}
        </span>
      </div>
      {queued && status.queue_position ? (
        <p className="mt-2 rounded-md bg-blue-50 p-3 text-sm text-blue-950" role="status">
          Waiting for a free slot — position {status.queue_position} in the queue.
        </p>
      ) : (
        <p className="mt-1 text-sm text-muted">This usually takes 15–60 seconds.</p>
      )}
      <ol className="mt-4 space-y-2" aria-live="polite">
        {STAGES.map(([key, label], i) => {
          const done = !queued && currentIndex > i;
          const current = !queued && currentIndex === i;
          return (
            <li key={key} className="flex items-center gap-3 text-sm">
              <span className="flex h-5 w-5 items-center justify-center" aria-hidden="true">
                {done ? <span className="font-bold text-emerald-700">✓</span> : current ? <Spinner /> : "○"}
              </span>
              <span className={done ? "text-ink" : current ? "font-semibold text-ink" : "text-muted"}>
                {label}
                <span className="sr-only">
                  {done ? " (finished)" : current ? " (in progress)" : " (waiting)"}
                </span>
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
