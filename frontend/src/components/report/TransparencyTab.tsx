import type { Report } from "../../api/types";
import { formatDuration } from "../../utils/format";
import { TOOL_STATUS_TEXT } from "../../utils/labels";
import { PlainText } from "../PlainText";

function Row({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-line py-3 sm:grid-cols-[220px_1fr]">
      <dt className="font-semibold">{term}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

export function TransparencyTab({ report }: { report: Report }) {
  const t = report.transparency;
  const c = t.consistency;
  const providerName =
    t.llm_provider === "gemini"
      ? "Google Gemini"
      : t.llm_provider === "mock"
        ? "Offline mock (demo)"
        : t.llm_provider;
  return (
    <div className="space-y-5">
      <dl className="card">
        <Row term="AI model and provider">
          {providerName} — <span className="font-mono">{t.model_name ?? "—"}</span>
          {t.data_use_notice && <p className="mt-1 text-amber-900">{t.data_use_notice}</p>}
        </Row>
        <Row term="Prompt version">
          <span className="font-mono">{t.prompt_version}</span> · {t.llm_requests} AI request(s) made
        </Row>
        <Row term="Code executed">
          <strong>No.</strong> The code was only read and analysed as text; it was never run.
        </Row>
        <Row term="Secrets masked">
          {t.redaction.count === 0
            ? "No secrets were detected."
            : `${t.redaction.count} value(s) were masked before the code was sent to the AI: ${Object.entries(
                t.redaction.by_type,
              )
                .map(([type, n]) => `${type} × ${n}`)
                .join(", ")}.`}
        </Row>
        <Row term="Consistency check">
          {!c.enabled
            ? `Not run${c.reason ? ` (${c.reason})` : ""}.`
            : c.run_b_ok === false
              ? "The second AI check could not be completed."
              : `A second, independent AI review was compared with the main one: ${c.matched} finding(s) matched, ${c.only_in_a} appeared only in the main review.`}
          {c.enabled && c.only_in_b > 0 && (
            <p className="mt-1">
              The second check found {c.only_in_b} possible issue(s) not reported in the main explanation.
            </p>
          )}
        </Row>
        <Row term="Processing time">{formatDuration(t.processing_time_ms)}</Row>
        {t.code_storage_note && <Row term="Stored code">{t.code_storage_note}</Row>}
      </dl>

      <section className="card" aria-labelledby="tools-title">
        <h2 id="tools-title">Static analysis tools</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line">
                <th scope="col" className="py-2 pr-3">
                  Tool
                </th>
                <th scope="col" className="py-2 pr-3">
                  Version
                </th>
                <th scope="col" className="py-2 pr-3">
                  Status
                </th>
                <th scope="col" className="py-2 pr-3">
                  Findings
                </th>
                <th scope="col" className="py-2">
                  Message
                </th>
              </tr>
            </thead>
            <tbody>
              {t.tools_run.map((tool) => (
                <tr key={tool.tool} className="border-b border-line align-top">
                  <td className="py-2 pr-3 font-mono">{tool.tool}</td>
                  <td className="py-2 pr-3">{tool.version ?? "—"}</td>
                  <td className="py-2 pr-3">
                    <span className={tool.status === "ok" ? "text-emerald-800" : "text-amber-900"}>
                      {tool.status === "ok" ? "✓ " : "! "}
                      {TOOL_STATUS_TEXT[tool.status] ?? tool.status}
                    </span>
                  </td>
                  <td className="py-2 pr-3">{tool.findings_count}</td>
                  <td className="py-2">{tool.message ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid gap-5 md:grid-cols-2">
        <section className="card" aria-labelledby="checked-title">
          <h2 id="checked-title">What was checked</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {t.checked.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className="card" aria-labelledby="not-checked-title">
          <h2 id="not-checked-title">What was not checked</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {t.not_checked.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>

      <section className="card" aria-labelledby="limits-title">
        <h2 id="limits-title">Limitations of this report</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
          {t.limitations.map((item, i) => (
            <li key={i}>
              <PlainText text={item} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
