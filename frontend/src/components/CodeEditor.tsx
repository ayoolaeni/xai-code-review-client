import Editor from "@monaco-editor/react";
import { useState, type DragEvent } from "react";

import type { LanguageChoice } from "../api/types";
import { countLines } from "../utils/format";
import { EDITOR_LANGUAGE } from "../utils/monacoSetup";

export function CodeEditor({
  value,
  onChange,
  language,
  maxLines,
  maxChars,
  onFileDropped,
}: {
  value: string;
  onChange: (value: string) => void;
  language: LanguageChoice;
  maxLines: number;
  maxChars: number;
  onFileDropped?: (file: File) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const lines = countLines(value);
  const overLines = lines > maxLines;
  const overChars = value.length > maxChars;
  const over = overLines || overChars;

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && onFileDropped) onFileDropped(file);
  }

  return (
    <div>
      <div
        className={`relative h-[260px] overflow-hidden rounded-md border sm:h-[360px] ${
          over
            ? "border-red-700 ring-2 ring-red-700"
            : dragging
              ? "border-blue-700 ring-2 ring-blue-700"
              : "border-line"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        data-testid="code-editor"
      >
        <Editor
          height="100%"
          language={EDITOR_LANGUAGE[language]}
          value={value}
          onChange={(v) => onChange(v ?? "")}
          options={{
            minimap: { enabled: false },
            lineNumbers: "on",
            fontSize: 13,
            scrollBeyondLastLine: false,
            wordWrap: "off",
            automaticLayout: true,
            tabSize: 4,
            ariaLabel: "Source code editor. Paste your code here.",
          }}
        />
        {!value && (
          <div className="pointer-events-none absolute left-16 top-1 font-mono text-[13px] text-muted">
            Paste your code here…
          </div>
        )}
        {dragging && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-blue-50/80 text-sm font-semibold text-blue-900">
            Drop the file to load it
          </div>
        )}
      </div>
      <p
        className={`mt-1 text-right text-xs ${over ? "font-semibold text-red-800" : "text-muted"}`}
        aria-live="polite"
        data-testid="line-counter"
      >
        Lines: {lines} / {maxLines}
        {overChars && ` · Characters: ${value.length} / ${maxChars}`}
        {over && " — too long, please shorten your code"}
      </p>
    </div>
  );
}
