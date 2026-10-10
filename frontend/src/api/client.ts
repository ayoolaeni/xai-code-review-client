// Typed fetch client. Every API call goes through `request` (credentials included, typed errors).
import type {
  AdminUser,
  AnalysisCreate,
  AnalysisCreated,
  AnalysisResponse,
  ApiErrorBody,
  FeedbackIn,
  Health,
  HistoryItem,
  Meta,
  Page,
  SettingInfo,
  Stats,
  User,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly retryAfter: number | null;

  constructor(status: number, code: string, message: string, details?: unknown, retryAfter?: number | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.retryAfter = retryAfter ?? null;
  }
}

const NETWORK_MESSAGE = "Could not reach the server. Check your connection and try again.";

export async function request<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const finalHeaders: Record<string, string> = { Accept: "application/json", ...(headers as object) };
  let body = rest.body;
  if (json !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  }
  let response: Response;
  try {
    response = await fetch(path, { ...rest, body, headers: finalHeaders, credentials: "include" });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", NETWORK_MESSAGE);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }
  if (!response.ok) {
    const err = (data as ApiErrorBody | null)?.error;
    const retryHeader = response.headers.get("Retry-After");
    throw new ApiError(
      response.status,
      err?.code ?? `HTTP_${response.status}`,
      err?.message ?? `The request failed (HTTP ${response.status}).`,
      err?.details,
      retryHeader ? Number(retryHeader) : null,
    );
  }
  return data as T;
}

export const api = {
  // meta
  meta: () => request<Meta>("/api/meta"),
  health: () => request<Health>("/api/health"),

  // auth
  me: () => request<User>("/api/auth/me"),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", { method: "POST", json: { email, password } }),
  register: (body: { full_name: string; email: string; password: string; store_code_default: boolean }) =>
    request<User>("/api/auth/register", { method: "POST", json: body }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  updateMe: (body: { full_name?: string; store_code_default?: boolean }) =>
    request<User>("/api/auth/me", { method: "PATCH", json: body }),

  // analyses
  createAnalysis: (body: AnalysisCreate) =>
    request<AnalysisCreated>("/api/analyses", { method: "POST", json: body }),
  getAnalysis: (publicId: string, feedbackToken?: string | null) =>
    request<AnalysisResponse>(
      `/api/analyses/${encodeURIComponent(publicId)}${feedbackToken ? `?ft=${encodeURIComponent(feedbackToken)}` : ""}`,
    ),
  deleteAnalysis: (publicId: string) =>
    request<void>(`/api/analyses/${encodeURIComponent(publicId)}`, { method: "DELETE" }),
  sendFeedback: (publicId: string, body: FeedbackIn) =>
    request<{ feedback_id: number; feedback_token: string | null }>(
      `/api/analyses/${encodeURIComponent(publicId)}/feedback`,
      { method: "POST", json: body },
    ),
  pdfUrl: (publicId: string) => `/api/analyses/${encodeURIComponent(publicId)}/pdf`,

  // history
  history: (params: { page: number; page_size: number; language?: string; q?: string }) => {
    const qs = new URLSearchParams({ page: String(params.page), page_size: String(params.page_size) });
    if (params.language) qs.set("language", params.language);
    if (params.q) qs.set("q", params.q);
    return request<Page<HistoryItem>>(`/api/history?${qs.toString()}`);
  },

  // admin
  adminUsers: (page: number, q: string) =>
    request<Page<AdminUser>>(`/api/admin/users?page=${page}&q=${encodeURIComponent(q)}`),
  adminUpdateUser: (userId: number, body: { role?: "user" | "admin"; is_active?: boolean }) =>
    request<AdminUser>(`/api/admin/users/${userId}`, { method: "PATCH", json: body }),
  adminDeleteUser: (userId: number) => request<void>(`/api/admin/users/${userId}`, { method: "DELETE" }),
  adminStats: (days: number) => request<Stats>(`/api/admin/stats?days=${days}`),
  adminSettings: () => request<SettingInfo[]>("/api/admin/settings"),
  adminUpdateSettings: (changes: Record<string, unknown>) =>
    request<SettingInfo[]>("/api/admin/settings", { method: "PUT", json: changes }),
};
