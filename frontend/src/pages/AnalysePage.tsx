import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../api/client";
import type { LanguageChoice } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { CodeEditor } from "../components/CodeEditor";
import { ErrorAlert } from "../components/Feedback";
import {
  FileUploadButton,
  LanguageSelect,
  PrivacyNotice,
  StoreCodeToggle,
} from "../components/InputControls";
import { PageSkeleton } from "../components/Skeleton";
import { countLines } from "../utils/format";
import { FileRejected, readSourceFile, type LoadedFile } from "../utils/files";

export function AnalysePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: 5 * 60_000 });

  const [code, setCode] = useState("");
  const [language, setLanguage] = useState<LanguageChoice>("auto");
  const [filename, setFilename] = useState<string | null>(null);
  const [storeCode, setStoreCode] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ title: string; message: string } | null>(null);

  useEffect(() => {
    if (user) setStoreCode(user.store_code_default);
  }, [user]);

  useEffect(() => {
    document.title = "Analyse code · Explainable AI Code Review Assistant";
  }, []);

  if (meta.isLoading) return <PageSkeleton />;
  if (meta.isError || !meta.data) {
    return <ErrorAlert message="The page could not load its settings." onRetry={() => meta.refetch()} />;
  }
  const { max_lines: maxLines, max_chars: maxChars } = meta.data;

  const lines = countLines(code);
  const empty = code.trim().length === 0;
  const tooLong = lines > maxLines || code.length > maxChars;

  function loadFile(file: LoadedFile) {
    setCode(file.text);
    setFilename(file.name);
    setLanguage(file.language);
    setError(null);
  }

  async function onDrop(file: File) {
    try {
      loadFile(await readSourceFile(file));
    } catch (e) {
      setError({
        title: "File not accepted",
        message: e instanceof FileRejected ? e.message : "The file could not be read.",
      });
    }
  }

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.createAnalysis({
        code,
        language,
        filename,
        store_code: user ? storeCode : null,
      });
      navigate(`/report/${created.public_id}`);
    } catch (e) {
      if (e instanceof ApiError) {
        const title = e.status === 429 ? "Too many analyses" : "Your code could not be analysed";
        setError({ title, message: e.message });
      } else {
        setError({ title: "Your code could not be analysed", message: "An unexpected error occurred." });
      }
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1>Analyse your code</h1>
        <p className="mt-1 text-muted">
          Paste Python, JavaScript or Java code (up to {maxLines} lines). You will get a plain-language
          explanation, a list of risks with how sure we are about each one, and an improved version — and the
          code is never run.
        </p>
      </div>

      <PrivacyNotice text={meta.data.privacy_notice} />

      {error && <ErrorAlert title={error.title} message={error.message} />}

      <div className="card space-y-4">
        <div className="grid gap-4 sm:grid-cols-[minmax(0,220px)_1fr] sm:items-end">
          <LanguageSelect value={language} onChange={setLanguage} />
          <FileUploadButton onLoaded={loadFile} filename={filename} />
        </div>

        <CodeEditor
          value={code}
          onChange={(v) => {
            setCode(v);
            if (error) setError(null);
          }}
          language={language}
          maxLines={maxLines}
          maxChars={maxChars}
          onFileDropped={onDrop}
        />

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          {user ? <StoreCodeToggle checked={storeCode} onChange={setStoreCode} /> : <span />}
          <div className="flex gap-3">
            {code && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setCode("");
                  setFilename(null);
                  setError(null);
                }}
              >
                Clear
              </button>
            )}
            <button
              type="button"
              className="btn-primary min-w-[140px]"
              onClick={submit}
              disabled={empty || tooLong || submitting}
              data-testid="analyse-button"
            >
              {submitting ? "Starting…" : "Analyse"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
