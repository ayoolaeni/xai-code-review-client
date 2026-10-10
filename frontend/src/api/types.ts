// Mirrors the backend contract (spec Sections 7 and 9).

export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type RiskLevel = Severity | "NONE";
export type Confidence = "HIGH" | "MEDIUM" | "LOW";
export type Category = "security" | "reliability" | "performance" | "maintainability";
export type Source = "static" | "llm" | "both";
export type LanguageId = "python" | "javascript" | "java";
export type LanguageChoice = "auto" | LanguageId;

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}

// ---------- meta ----------
export interface LanguageInfo {
  id: LanguageId;
  label: string;
  extensions: string[];
}

export interface Meta {
  languages: LanguageInfo[];
  max_lines: number;
  max_chars: number;
  guest_retention_hours: number;
  privacy_notice: string;
  llm_provider: string;
}

export interface Health {
  status: string;
  db: string;
  llm_provider: string;
  llm_model: string;
  llm: string;
  llm_quota_today: { used: number; limit: number };
  tools: Record<string, boolean>;
}

// ---------- auth ----------
export interface User {
  user_id: number;
  full_name: string;
  email: string;
  role: "user" | "admin";
  store_code_default: boolean;
  created_at: string;
}

// ---------- analyses ----------
export interface AnalysisCreate {
  code: string;
  language: LanguageChoice;
  filename?: string | null;
  store_code?: boolean | null;
}

export interface AnalysisCreated {
  public_id: string;
  status: "queued";
}

export type JobStatus = "queued" | "running" | "completed" | "failed";

export interface AnalysisStatus {
  public_id: string;
  status: Exclude<JobStatus, "completed">;
  stage: string;
  stage_label: string;
  stage_index: number;
  stage_count: number;
  queue_position: number | null;
  started_at: string | null;
  error_message: string | null;
}

export interface Cwe {
  id: string;
  name: string;
  url: string;
}

export interface Finding {
  key: string;
  category: Category;
  title: string;
  description: string;
  evidence: string | null;
  recommendation: string;
  start_line: number;
  end_line: number;
  severity: Severity;
  confidence: Confidence;
  confidence_reason: string;
  cwe: Cwe | null;
  owasp_category: string | null;
  source: Source;
  static_tool: string | null;
  static_rule_id: string | null;
  ai_assessment: "agree" | "likely_false_positive" | "not_reviewed" | null;
}

export interface Section {
  start_line: number;
  end_line: number;
  title: string;
  explanation: string;
}

export interface Change {
  number: number;
  description: string;
  reason: string;
  related_findings: string[];
  original_lines: [number, number] | null;
}

export interface ImprovedCheck {
  syntax_ok: boolean | null;
  syntax_message: string | null;
  remaining_static_findings: number | null;
  new_high_or_critical: number | null;
}

export interface ToolRun {
  tool: string;
  version: string | null;
  status: "ok" | "failed" | "skipped" | "unavailable" | "timeout";
  findings_count: number;
  message: string | null;
}

export interface Consistency {
  enabled: boolean;
  run_b_ok: boolean | null;
  matched: number;
  only_in_a: number;
  only_in_b: number;
  reason?: string | null;
}

export interface Report {
  public_id: string;
  status: "completed";
  created_at: string;
  completed_at: string | null;
  processing_time_ms: number | null;
  expires_at: string | null;
  owner: "guest" | "user";
  submission: {
    language: LanguageId;
    language_label: string;
    language_source: "user" | "auto";
    filename: string | null;
    line_count: number;
    code_stored: boolean;
    original_code: string | null;
    redacted_code: string | null;
  };
  overview: {
    purpose_summary: string;
    overall_risk_level: RiskLevel;
    overall_confidence: Confidence;
    human_review_advised: boolean;
    review_reasons: string[];
    no_review_message?: string | null;
    ai_explanation_available: boolean;
    ai_unavailable_reason: string | null;
    ai_unavailable_message?: string | null;
    ai_unavailable_until: string | null;
    counts: { CRITICAL: number; HIGH: number; MEDIUM: number; LOW: number; total: number };
    sensitive_domains: string[];
  };
  breakdown: Section[];
  findings: Finding[];
  improved: {
    available: boolean;
    improved_code: string | null;
    changes: Change[];
    check: ImprovedCheck | null;
    requires_acknowledgement: boolean;
    has_problems?: boolean;
  };
  transparency: {
    model_name: string | null;
    llm_provider: string | null;
    data_use_notice: string | null;
    prompt_version: string | null;
    llm_requests: number;
    tools_run: ToolRun[];
    redaction: { count: number; by_type: Record<string, number> };
    consistency: Consistency;
    checked: string[];
    not_checked: string[];
    limitations: string[];
    code_executed: false;
    processing_time_ms: number | null;
    code_storage_note: string | null;
  };
  feedback: { rating: number | null; was_helpful: boolean | null; comment: string | null };
}

export type AnalysisResponse = Report | AnalysisStatus;

export function isReport(r: AnalysisResponse): r is Report {
  return r.status === "completed";
}

export interface FeedbackIn {
  rating: number;
  was_helpful: boolean;
  comment?: string | null;
  feedback_token?: string | null;
}

// ---------- history ----------
export interface HistoryItem {
  public_id: string;
  submitted_at: string;
  language: LanguageId;
  filename: string | null;
  line_count: number;
  status: JobStatus;
  overall_risk_level: RiskLevel | null;
  overall_confidence: Confidence | null;
  human_review_advised: boolean | null;
  purpose_summary_preview: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ---------- admin ----------
export interface AdminUser extends User {
  is_active: boolean;
  last_login_at: string | null;
  analysis_count: number;
}

export interface SettingInfo {
  key: string;
  value: unknown;
  default: unknown;
  type: "int" | "float" | "bool" | "tools";
  min: number | null;
  max: number | null;
  description: string;
  options: Record<string, string[]> | null;
}

export interface Stats {
  range_days: number;
  totals: {
    analyses: number;
    completed: number;
    failed: number;
    fallback: number;
    registered_users: number;
    guest_analyses: number;
  };
  per_day: { date: string; analyses: number }[];
  by_language: Record<string, number>;
  avg_processing_ms: number | null;
  p90_processing_ms: number | null;
  findings_by_severity: Record<Severity, number>;
  findings_by_source: Record<Source, number>;
  human_review_advised_rate: number | null;
  feedback: { count: number; avg_rating: number | null; helpful_rate: number | null };
  tool_failures: Record<string, number>;
  llm_usage_today: { requests: number; limit: number; input_tokens: number; output_tokens: number };
  llm_usage_history: { date: string; requests: number; input_tokens: number; output_tokens: number }[];
}
