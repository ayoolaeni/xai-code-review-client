import { useEffect, useRef, useState } from "react";

import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "./Toast";

export function AccountSettingsDialog({ onClose }: { onClose: () => void }) {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user?.full_name ?? "");
  const [storeCode, setStoreCode] = useState(user?.store_code_default ?? false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const firstField = useRef<HTMLInputElement>(null);

  useEffect(() => {
    firstField.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!user) return null;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateMe({ full_name: name, store_code_default: storeCode });
      setUser(updated);
      toast("Your settings were saved.");
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save your settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 text-ink">
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        onSubmit={save}
        className="w-full max-w-md rounded-lg bg-surface p-6 shadow-xl"
      >
        <h2 id="settings-title">Account settings</h2>
        <div className="mt-4">
          <label htmlFor="settings-name" className="label">
            Name
          </label>
          <input
            id="settings-name"
            ref={firstField}
            className="input"
            value={name}
            maxLength={120}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <div className="mt-4 flex items-start gap-2">
          <input
            id="settings-store"
            type="checkbox"
            className="mt-1 h-4 w-4"
            checked={storeCode}
            onChange={(e) => setStoreCode(e.target.checked)}
          />
          <div>
            <label htmlFor="settings-store" className="text-sm font-semibold">
              Keep my code in my history by default
            </label>
            <p className="hint">
              When this is off, your original code is deleted as soon as the report is ready. The report keeps
              a copy with secrets masked so the comparison still works.
            </p>
          </div>
        </div>
        {error && (
          <p role="alert" className="mt-3 text-sm text-red-800">
            {error}
          </p>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}
