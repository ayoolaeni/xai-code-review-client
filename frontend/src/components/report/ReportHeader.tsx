import { useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../../api/client";
import type { Report } from "../../api/types";
import { formatDateTime, shortId } from "../../utils/format";
import { useToast } from "../Toast";

/** Fetch the PDF first so a server error is shown as a message instead of being saved as a file. */
function DownloadPdfButton({ publicId }: { publicId: string }) {
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  async function download() {
    setBusy(true);
    try {
      const res = await fetch(api.pdfUrl(publicId), { credentials: "include" });
      if (!res.ok) {
        let message = `The PDF could not be created (HTTP ${res.status}).`;
        try {
          message = (await res.json()).error?.message ?? message;
        } catch {
          /* not JSON */
        }
        throw new ApiError(res.status, "PDF_FAILED", message);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `xai-report-${publicId.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "The PDF could not be downloaded.", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <button type="button" className="btn-secondary" onClick={download} disabled={busy}>
      <span aria-hidden="true">⤓</span> {busy ? "Preparing PDF…" : "Download PDF"}
    </button>
  );
}

export function ReportHeader({ report }: { report: Report }) {
  const sub = report.submission;
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h1>Code review report</h1>
        <p className="mt-1 text-sm text-muted">
          Report <span className="font-mono">{shortId(report.public_id)}</span> · {sub.language_label}
          {sub.language_source === "auto" && " (detected)"} · {sub.line_count} lines
          {sub.filename && (
            <>
              {" "}
              · <span className="font-mono">{sub.filename}</span>
            </>
          )}{" "}
          · {formatDateTime(report.created_at)}
        </p>
        {report.expires_at && (
          <p className="mt-1 text-xs text-muted">
            Guest report: it will be deleted on {formatDateTime(report.expires_at)}. Keep the link or download
            the PDF to keep a copy.
          </p>
        )}
      </div>
      <div className="flex shrink-0 gap-2">
        <DownloadPdfButton publicId={report.public_id} />
        <Link to="/" className="btn-primary no-underline hover:no-underline">
          New analysis
        </Link>
      </div>
    </div>
  );
}

export function FallbackBanner({ report }: { report: Report }) {
  const o = report.overview;
  if (o.ai_explanation_available) return null;
  let localReset: string | null = null;
  if (o.ai_unavailable_reason === "quota_exhausted" && o.ai_unavailable_until) {
    localReset = new Date(o.ai_unavailable_until).toLocaleString(undefined, {
      weekday: "short",
      hour: "numeric",
      minute: "2-digit",
    });
  }
  return (
    <div role="alert" className="rounded-lg border-2 border-amber-400 bg-amber-50 p-4 text-amber-950">
      <p className="font-semibold">⚠ AI explanation not available</p>
      <p className="mt-1 text-sm">{o.ai_unavailable_message}</p>
      {localReset && <p className="mt-1 text-sm">In your time zone that is {localReset}.</p>}
    </div>
  );
}
