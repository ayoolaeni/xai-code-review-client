// AI output and tool messages are rendered as plain text only — never as HTML or Markdown —
// so neither submitted code nor model output can inject markup (spec Section 11.1).
import { Fragment } from "react";

export function PlainText({ text, className = "" }: { text: string | null | undefined; className?: string }) {
  if (!text) return null;
  const parts = text.split("`");
  return (
    <span className={`whitespace-pre-line break-words ${className}`}>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <code key={i} className="rounded bg-canvas px-1 py-0.5 font-mono text-[0.9em]">
            {part}
          </code>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </span>
  );
}
