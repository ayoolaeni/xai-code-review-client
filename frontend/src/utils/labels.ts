import type { Category, Confidence, RiskLevel, Source } from "../api/types";

export const SEVERITY_ORDER: Record<RiskLevel, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, NONE: 0 };
export const CONFIDENCE_ORDER: Record<Confidence, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 };

export function titleCase(level: string): string {
  return level.charAt(0) + level.slice(1).toLowerCase();
}

// Severity badges: text label + colour (NFR8). Contrast ≥ 4.5:1 for every pair.
export const SEVERITY_CLASSES: Record<RiskLevel, string> = {
  CRITICAL: "bg-sev-critical text-white border-sev-critical",
  HIGH: "bg-sev-high text-white border-sev-high",
  MEDIUM: "bg-sev-medium-bg text-sev-medium border-sev-medium",
  LOW: "bg-sev-low-bg text-sev-low border-sev-low",
  NONE: "bg-surface text-muted border-line",
};

export const SEVERITY_BORDER: Record<RiskLevel, string> = {
  CRITICAL: "border-l-sev-critical",
  HIGH: "border-l-sev-high",
  MEDIUM: "border-l-sev-medium",
  LOW: "border-l-sev-low",
  NONE: "border-l-line",
};

export const CONFIDENCE_CLASSES: Record<Confidence, string> = {
  HIGH: "border-emerald-700 text-emerald-800",
  MEDIUM: "border-amber-700 text-amber-800",
  LOW: "border-red-700 text-red-800",
};

export const SOURCE_TEXT: Record<Source, string> = {
  both: "static analysis + AI",
  static: "static analysis only",
  llm: "AI only",
};

export const CATEGORY_TEXT: Record<Category, string> = {
  security: "Security",
  reliability: "Reliability",
  performance: "Performance",
  maintainability: "Maintainability",
};

export const AI_ASSESSMENT_TEXT: Record<string, string> = {
  agree: "agrees this is a real problem",
  likely_false_positive: "thinks this may be a false positive",
  not_reviewed: "did not review it",
};

export const TOOL_STATUS_TEXT: Record<string, string> = {
  ok: "Ran successfully",
  failed: "Failed",
  skipped: "Skipped",
  unavailable: "Not installed",
  timeout: "Timed out",
};
