import { useEffect, useRef, useState } from "react";

import type { Finding } from "../../api/types";
import { lineRange } from "../../utils/format";
import { AI_ASSESSMENT_TEXT, CATEGORY_TEXT, SEVERITY_BORDER } from "../../utils/labels";
import { Chip, ConfidenceBadge, SeverityBadge, SourceBadge } from "../Badges";
import { PlainText } from "../PlainText";
import { CodeExcerpt } from "./CodeExcerpt";

export function FindingCard({
  finding: f,
  code,
  expanded,
  onToggle,
  scrollIntoView = false,
}: {
  finding: Finding;
  code: string;
  expanded: boolean;
  onToggle: (open: boolean) => void;
  scrollIntoView?: boolean;
}) {
  const [showCode, setShowCode] = useState(false);
  const ref = useRef<HTMLElement>(null);
  const bodyId = `finding-body-${f.key}`;

  useEffect(() => {
    if (scrollIntoView && ref.current) {
      ref.current.scrollIntoView?.({ behavior: "smooth", block: "start" });
      ref.current.querySelector<HTMLButtonElement>("button")?.focus();
    }
  }, [scrollIntoView]);

  return (
    <article
      ref={ref}
      id={`finding-${f.key}`}
      className={`rounded-lg border border-l-4 border-line bg-surface shadow-sm ${SEVERITY_BORDER[f.severity]}`}
      data-testid="finding-card"
    >
      <h3 className="text-base">
        <button
          type="button"
          className="flex w-full flex-col gap-2 p-4 text-left"
          aria-expanded={expanded}
          aria-controls={bodyId}
          onClick={() => onToggle(!expanded)}
        >
          <span className="flex items-start justify-between gap-3">
            <span className="font-semibold">
              <span className="font-mono text-muted">{f.key}</span> <PlainText text={f.title} />
              <span className="ml-2 text-sm font-normal text-muted">
                ({lineRange(f.start_line, f.end_line)})
              </span>
            </span>
            <span aria-hidden="true" className="text-muted">
              {expanded ? "▲" : "▼"}
            </span>
          </span>
          <span className="flex flex-wrap items-center gap-2 font-normal">
            <SeverityBadge level={f.severity} />
            <ConfidenceBadge level={f.confidence} />
            <SourceBadge source={f.source} />
            <Chip>{CATEGORY_TEXT[f.category]}</Chip>
            {f.owasp_category && <Chip>{f.owasp_category}</Chip>}
          </span>
        </button>
      </h3>
      {f.cwe && (
        <p className="-mt-2 px-4 pb-2 text-sm">
          Weakness:{" "}
          <a href={f.cwe.url} target="_blank" rel="noopener noreferrer">
            {f.cwe.id} – {f.cwe.name}
            <span className="sr-only"> (opens the MITRE CWE page in a new tab)</span>
          </a>
        </p>
      )}
      {expanded && (
        <div id={bodyId} className="space-y-3 border-t border-line px-4 py-4 text-sm">
          <div>
            <h4 className="font-semibold">Why it matters</h4>
            <p>
              <PlainText text={f.description} />
            </p>
          </div>
          {f.evidence && (
            <div>
              <h4 className="font-semibold">Evidence</h4>
              <pre className="code-block whitespace-pre-wrap">{f.evidence}</pre>
            </div>
          )}
          <div>
            <h4 className="font-semibold">How to fix</h4>
            <p>
              <PlainText text={f.recommendation} />
            </p>
          </div>
          <div>
            <h4 className="font-semibold">Why this confidence</h4>
            <p>
              <PlainText text={f.confidence_reason} />
            </p>
          </div>
          {f.source !== "llm" && (
            <p className="text-muted">
              Static analysis: <span className="font-mono">{f.static_tool}</span>
              {f.static_rule_id && (
                <>
                  {" "}
                  (rule <span className="font-mono">{f.static_rule_id}</span>)
                </>
              )}
            </p>
          )}
          {f.source === "static" && f.ai_assessment && (
            <p>
              <span className="font-semibold">AI&apos;s view:</span> {AI_ASSESSMENT_TEXT[f.ai_assessment]}
            </p>
          )}
          {code && (
            <div>
              <button
                type="button"
                className="btn-link"
                aria-expanded={showCode}
                onClick={() => setShowCode((s) => !s)}
              >
                {showCode ? "Hide code" : "Show in code"}
              </button>
              {showCode && (
                <div className="mt-2">
                  <CodeExcerpt code={code} start={f.start_line} end={f.end_line} />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  );
}
