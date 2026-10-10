import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, ApiError } from "../../api/client";
import type { SettingInfo } from "../../api/types";
import { AdminNav } from "../../components/admin/AdminNav";
import { ErrorAlert } from "../../components/Feedback";
import { PageSkeleton } from "../../components/Skeleton";
import { useToast } from "../../components/Toast";

const LABELS: Record<string, string> = {
  max_lines: "Maximum lines per submission",
  max_chars: "Maximum characters per submission",
  guest_retention_hours: "Guest data retention (hours)",
  guest_rate_limit_per_hour: "Guest analyses per hour (per IP)",
  user_rate_limit_per_hour: "Registered-user analyses per hour",
  consistency_check_enabled: "Run the consistency check",
  enabled_tools: "Static analysis tools per language",
  llm_temperature: "AI temperature",
};

function fieldError(s: SettingInfo, value: unknown): string | null {
  if (s.type === "int" || s.type === "float") {
    const n = Number(value);
    if (value === "" || Number.isNaN(n)) return "Please enter a number.";
    if (s.type === "int" && !Number.isInteger(n)) return "Please enter a whole number.";
    if ((s.min != null && n < s.min) || (s.max != null && n > s.max))
      return `Must be between ${s.min} and ${s.max}.`;
  }
  return null;
}

export function AdminSettingsPage() {
  const settings = useQuery({ queryKey: ["admin-settings"], queryFn: api.adminSettings });
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const toast = useToast();

  useEffect(() => {
    document.title = "Analysis settings · Administration";
  }, []);
  useEffect(() => {
    if (settings.data) setDraft(Object.fromEntries(settings.data.map((s) => [s.key, s.value])));
  }, [settings.data]);

  if (settings.isLoading) return <PageSkeleton />;
  if (settings.isError || !settings.data) {
    return <ErrorAlert message="Settings could not be loaded." onRetry={() => settings.refetch()} />;
  }
  const defs = settings.data;
  const errors = Object.fromEntries(defs.map((s) => [s.key, fieldError(s, draft[s.key])]));
  const hasErrors = Object.values(errors).some(Boolean);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (hasErrors) return;
    setSaving(true);
    setServerError(null);
    const changes: Record<string, unknown> = {};
    for (const s of defs) {
      let v = draft[s.key];
      if (s.type === "int" || s.type === "float") v = Number(v);
      if (JSON.stringify(v) !== JSON.stringify(s.value)) changes[s.key] = v;
    }
    try {
      if (Object.keys(changes).length > 0) {
        await api.adminUpdateSettings(changes);
        await queryClient.invalidateQueries({ queryKey: ["admin-settings"] });
        await queryClient.invalidateQueries({ queryKey: ["meta"] });
      }
      toast("Settings saved. They take effect within 30 seconds.");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Settings could not be saved.";
      setServerError(msg);
      toast(msg, "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <h1>Administration</h1>
      <AdminNav />
      <form className="space-y-4" onSubmit={save} noValidate>
        {serverError && <ErrorAlert title="Not saved" message={serverError} />}
        {defs.map((s) => {
          const value = draft[s.key];
          const err = errors[s.key];
          const id = `setting-${s.key}`;
          const isDefault = JSON.stringify(value) === JSON.stringify(s.default);
          return (
            <div key={s.key} className="card">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  {s.type === "bool" ? (
                    <label htmlFor={id} className="flex items-center gap-2 font-semibold">
                      <input
                        id={id}
                        type="checkbox"
                        checked={Boolean(value)}
                        onChange={(e) => setDraft((d) => ({ ...d, [s.key]: e.target.checked }))}
                      />
                      {LABELS[s.key] ?? s.key}
                    </label>
                  ) : (
                    <label htmlFor={s.type === "tools" ? undefined : id} className="label">
                      {LABELS[s.key] ?? s.key}
                    </label>
                  )}
                  <p className="hint">
                    {s.description} {s.min != null && `Allowed: ${s.min}–${s.max}. `}Default:{" "}
                    {JSON.stringify(s.default)}.
                  </p>
                </div>
                <button
                  type="button"
                  className="btn-link"
                  disabled={isDefault}
                  onClick={() => setDraft((d) => ({ ...d, [s.key]: s.default }))}
                >
                  Reset to default
                </button>
              </div>
              {(s.type === "int" || s.type === "float") && (
                <input
                  id={id}
                  type="number"
                  className="input mt-2 max-w-xs"
                  value={String(value ?? "")}
                  min={s.min ?? undefined}
                  max={s.max ?? undefined}
                  step={s.type === "float" ? 0.1 : 1}
                  aria-invalid={!!err}
                  aria-describedby={err ? `${id}-error` : undefined}
                  onChange={(e) => setDraft((d) => ({ ...d, [s.key]: e.target.value }))}
                />
              )}
              {s.type === "tools" && s.options && (
                <div className="mt-2 grid gap-3 sm:grid-cols-3">
                  {Object.entries(s.options).map(([lang, tools]) => {
                    const current = ((value as Record<string, string[]>) ?? {})[lang] ?? [];
                    return (
                      <fieldset key={lang} className="rounded-md border border-line p-3">
                        <legend className="px-1 text-sm font-semibold capitalize">{lang}</legend>
                        {tools.map((tool) => (
                          <label key={tool} className="flex items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              checked={current.includes(tool)}
                              onChange={(e) => {
                                const next = e.target.checked
                                  ? [...current, tool]
                                  : current.filter((t) => t !== tool);
                                setDraft((d) => ({
                                  ...d,
                                  [s.key]: { ...(d[s.key] as Record<string, string[]>), [lang]: next },
                                }));
                              }}
                            />
                            {tool}
                          </label>
                        ))}
                      </fieldset>
                    );
                  })}
                </div>
              )}
              {err && (
                <p id={`${id}-error`} role="alert" className="mt-1 text-sm font-semibold text-red-800">
                  {err}
                </p>
              )}
            </div>
          );
        })}
        <button type="submit" className="btn-primary" disabled={saving || hasErrors}>
          {saving ? "Saving…" : "Save settings"}
        </button>
      </form>
    </div>
  );
}
