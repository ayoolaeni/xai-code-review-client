import type { Confidence, RiskLevel, Source } from "../api/types";
import { CONFIDENCE_CLASSES, SEVERITY_CLASSES, SOURCE_TEXT, titleCase } from "../utils/labels";

const BASE =
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap";

export function SeverityBadge({ level, prefix = "Severity" }: { level: RiskLevel; prefix?: string }) {
  const text = level === "NONE" ? "None" : titleCase(level);
  return (
    <span className={`${BASE} ${SEVERITY_CLASSES[level]}`} data-testid="severity-badge">
      {prefix ? `${prefix}: ` : ""}
      {text}
    </span>
  );
}

export function ConfidenceBadge({ level, prefix = "Confidence" }: { level: Confidence; prefix?: string }) {
  return (
    <span className={`${BASE} bg-surface ${CONFIDENCE_CLASSES[level]}`} data-testid="confidence-badge">
      {prefix ? `${prefix}: ` : ""}
      {titleCase(level)}
    </span>
  );
}

export function SourceBadge({ source }: { source: Source }) {
  const icon = source === "both" ? "◆" : source === "static" ? "▣" : "✦";
  return (
    <span className={`${BASE} border-line bg-canvas text-ink`} data-testid="source-badge">
      <span aria-hidden="true">{icon}</span>
      Found by: {SOURCE_TEXT[source]}
    </span>
  );
}

export function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-line bg-canvas px-2 py-0.5 text-xs text-ink">
      {children}
    </span>
  );
}
