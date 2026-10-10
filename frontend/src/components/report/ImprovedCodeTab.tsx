import { DiffEditor } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import { useEffect, useRef, useState } from "react";

import type { Report } from "../../api/types";
import { lineRange } from "../../utils/format";
import { EDITOR_LANGUAGE } from "../../utils/monacoSetup";
import { useMediaQuery } from "../../utils/useMediaQuery";
import { EmptyState, InfoBox } from "../Feedback";
import { PlainText } from "../PlainText";

export function criticalKeys(report: Report): string[] {
  return report.findings.filter((f) => f.severity === "CRITICAL").map((f) => f.key);
}

/** Section 11.5: the diff is hidden (not rendered) until every CRITICAL finding has been opened. */
export function AcknowledgementGate({
  report,
  opened,
  onOpenFinding,
}: {
  report: Report;
  opened: Set<string>;
  onOpenFinding: (key: string) => void;
}) {
  const critical = report.findings.filter((f) => f.severity === "CRITICAL");
  return (
    <section
      aria-labelledby="gate-title"
      className="rounded-lg border-2 border-sev-critical bg-red-50 p-5"
      data-testid="ack-gate"
    >
      <h2 id="gate-title" className="text-red-900">
        This code has {critical.length} critical finding(s). Open and read each one before viewing the
        improved code.
      </h2>
      <p className="mt-1 text-sm">
        Understanding why the original code is dangerous helps you judge whether the suggested fix is right.
      </p>
      <ul className="mt-4 space-y-2">
        {critical.map((f) => {
          const done = opened.has(f.key);
          return (
            <li
              key={f.key}
              className="flex flex-wrap items-center gap-3 rounded-md border border-line bg-surface p-3"
            >
              <span aria-hidden="true" className={done ? "text-emerald-700" : "text-muted"}>
                {done ? "✓" : "○"}
              </span>
              <span className="flex-1 text-sm">
                <span className="font-mono text-muted">{f.key}</span> <PlainText text={f.title} /> (
                {lineRange(f.start_line, f.end_line)}){done && <span className="sr-only"> — read</span>}
              </span>
              <button type="button" className="btn-secondary" onClick={() => onOpenFinding(f.key)}>
                {done ? "Open again" : "Open"}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/**
 * Monaco diff view. The wrapper's own model clean-up disposes the text models before the diff widget
 * releases them ("TextModel got disposed before DiffEditorWidget model got reset" when leaving the tab),
 * so the models are kept on unmount and disposed here once the editor itself is gone.
 */
function ReadOnlyDiff({
  language,
  original,
  modified,
  inline,
}: {
  language: string;
  original: string;
  modified: string;
  inline: boolean;
}) {
  const models = useRef<editor.IDiffEditorModel | null>(null);
  useEffect(
    () => () => {
      const m = models.current;
      window.setTimeout(() => {
        m?.original.dispose();
        m?.modified.dispose();
      }, 0);
    },
    [],
  );
  return (
    <DiffEditor
      height="100%"
      language={language}
      original={original}
      modified={modified}
      keepCurrentOriginalModel
      keepCurrentModifiedModel
      onMount={(diffEditor) => {
        models.current = diffEditor.getModel();
      }}
      options={{
        readOnly: true,
        renderSideBySide: !inline,
        minimap: { enabled: false },
        fontSize: 13,
        automaticLayout: true,
        scrollBeyondLastLine: false,
      }}
    />
  );
}

export function ImprovedCodeTab({
  report,
  opened,
  onOpenFinding,
}: {
  report: Report;
  opened: Set<string>;
  onOpenFinding: (key: string) => void;
}) {
  const improved = report.improved;
  const inline = useMediaQuery("(max-width: 767px)");
  const [copied, setCopied] = useState(false);

  if (!improved.available || !improved.improved_code) {
    return (
      <EmptyState title="No improved version is available">
        The AI explanation was not available for this analysis, so no improved code was generated. Use the
        recommendations in the Risks tab to fix the problems by hand.
      </EmptyState>
    );
  }

  const required = criticalKeys(report);
  const gateOpen = improved.requires_acknowledgement && required.some((k) => !opened.has(k));
  if (gateOpen) {
    return <AcknowledgementGate report={report} opened={opened} onOpenFinding={onOpenFinding} />;
  }

  const original = report.submission.redacted_code ?? report.submission.original_code ?? "";
  const masked = report.transparency.redaction.count > 0;
  const check = improved.check;

  async function copy() {
    try {
      await navigator.clipboard.writeText(improved.improved_code ?? "");
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="space-y-4">
      {improved.requires_acknowledgement && (
        <p className="text-sm text-emerald-800" role="status">
          ✓ You reviewed the critical findings.
        </p>
      )}
      {improved.has_problems ? (
        <InfoBox tone="warning">
          <p className="font-semibold">
            Automatic checks found problems in the improved code. Do not copy it without reviewing it.
          </p>
          {check?.syntax_ok === false && <p className="mt-1">Syntax check failed: {check.syntax_message}</p>}
          {(check?.new_high_or_critical ?? 0) > 0 && (
            <p className="mt-1">
              {check?.new_high_or_critical} new high or critical security finding(s) were detected.
            </p>
          )}
        </InfoBox>
      ) : (
        <InfoBox tone={check?.syntax_ok ? "success" : "info"}>
          {check?.syntax_ok
            ? `Syntax check passed. Static analysis of the improved code found ${check.remaining_static_findings ?? 0} remaining issue(s) and no new serious ones.`
            : (check?.syntax_message ?? "The improved code could not be checked automatically.")}{" "}
          The improved code was generated by AI and was not executed — review it before use.
        </InfoBox>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted">
          Left: original{masked ? " (secrets masked)" : ""} · Right: improved
        </p>
        <button type="button" className="btn-secondary" onClick={copy}>
          {copied ? "Copied ✓" : "Copy improved code"}
        </button>
      </div>

      <div className="h-[420px] overflow-hidden rounded-md border border-line" data-testid="diff-editor">
        <ReadOnlyDiff
          language={EDITOR_LANGUAGE[report.submission.language]}
          original={original}
          modified={improved.improved_code}
          inline={inline}
        />
      </div>

      <section aria-labelledby="changes-title" className="card">
        <h2 id="changes-title">What changed and why</h2>
        {improved.changes.length === 0 ? (
          <p className="mt-2 text-sm text-muted">No changes were listed.</p>
        ) : (
          <ol className="mt-3 space-y-3">
            {improved.changes.map((c) => (
              <li key={c.number} className="rounded-md border border-line p-3 text-sm">
                <p className="font-semibold">
                  {c.number}. <PlainText text={c.description} />
                  {c.original_lines && (
                    <span className="ml-1 font-normal text-muted">
                      (original {lineRange(c.original_lines[0], c.original_lines[1])})
                    </span>
                  )}
                </p>
                <p className="mt-1">
                  <span className="font-semibold">Why: </span>
                  <PlainText text={c.reason} />
                </p>
                {c.related_findings.length > 0 && (
                  <p className="mt-1">
                    Fixes:{" "}
                    {c.related_findings.map((key, i) => (
                      <span key={key}>
                        {i > 0 && ", "}
                        <button type="button" className="btn-link" onClick={() => onOpenFinding(key)}>
                          {key}
                        </button>
                      </span>
                    ))}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
