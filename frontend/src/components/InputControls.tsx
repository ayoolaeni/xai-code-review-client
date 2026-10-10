import { useRef, useState } from "react";

import type { LanguageChoice } from "../api/types";
import { ACCEPTED_EXTENSIONS, FileRejected, readSourceFile, type LoadedFile } from "../utils/files";

export function LanguageSelect({
  value,
  onChange,
}: {
  value: LanguageChoice;
  onChange: (value: LanguageChoice) => void;
}) {
  return (
    <div>
      <label htmlFor="language" className="label">
        Language
      </label>
      <select
        id="language"
        className="input"
        value={value}
        onChange={(e) => onChange(e.target.value as LanguageChoice)}
      >
        <option value="auto">Auto-detect</option>
        <option value="python">Python</option>
        <option value="javascript">JavaScript</option>
        <option value="java">Java</option>
      </select>
    </div>
  );
}

export function FileUploadButton({
  onLoaded,
  filename,
}: {
  onLoaded: (file: LoadedFile) => void;
  filename: string | null;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  async function handle(file: File | undefined) {
    if (!file) return;
    setError(null);
    try {
      onLoaded(await readSourceFile(file));
    } catch (e) {
      setError(e instanceof FileRejected ? e.message : "The file could not be read.");
    } finally {
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div>
      <span className="label">Or upload one file</span>
      <input
        ref={inputRef}
        id="file-upload"
        type="file"
        accept={ACCEPTED_EXTENSIONS.join(",")}
        className="sr-only"
        onChange={(e) => handle(e.target.files?.[0])}
        data-testid="file-input"
      />
      <label htmlFor="file-upload" className="btn-secondary cursor-pointer">
        <span aria-hidden="true">⇪</span> Upload .py / .js / .java
      </label>
      {filename && !error && <p className="hint">Loaded: {filename}</p>}
      {error && (
        <p role="alert" className="mt-1 text-sm font-semibold text-red-800" data-testid="upload-error">
          {error}
        </p>
      )}
    </div>
  );
}

export function PrivacyNotice({ text }: { text: string }) {
  return (
    <aside
      className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950"
      aria-label="Privacy"
    >
      <span className="font-semibold">Privacy: </span>
      {text}
    </aside>
  );
}

export function StoreCodeToggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-start gap-2">
      <input
        id="store-code"
        type="checkbox"
        className="mt-1 h-4 w-4"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <div>
        <label htmlFor="store-code" className="text-sm font-semibold">
          Keep my code in my history
        </label>
        <p className="hint">If unchecked, your original code is deleted once the report is ready.</p>
      </div>
    </div>
  );
}
