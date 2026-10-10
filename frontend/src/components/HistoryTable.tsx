import { useNavigate } from "react-router-dom";

import type { HistoryItem } from "../api/types";
import { formatDateTime } from "../utils/format";
import { titleCase } from "../utils/labels";
import { ConfidenceBadge, SeverityBadge } from "./Badges";

const LANGUAGE_LABEL: Record<string, string> = { python: "Python", javascript: "JavaScript", java: "Java" };

export function HistoryTable({
  items,
  onDelete,
}: {
  items: HistoryItem[];
  onDelete: (item: HistoryItem) => void;
}) {
  const navigate = useNavigate();
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface">
      <table className="w-full min-w-[760px] text-left text-sm">
        <caption className="sr-only">Your past analyses</caption>
        <thead className="bg-canvas">
          <tr>
            <th scope="col" className="px-3 py-2">
              Date
            </th>
            <th scope="col" className="px-3 py-2">
              File / language
            </th>
            <th scope="col" className="px-3 py-2">
              Lines
            </th>
            <th scope="col" className="px-3 py-2">
              Overall risk
            </th>
            <th scope="col" className="px-3 py-2">
              Confidence
            </th>
            <th scope="col" className="px-3 py-2">
              Review advised
            </th>
            <th scope="col" className="px-3 py-2">
              Purpose
            </th>
            <th scope="col" className="px-3 py-2">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.public_id}
              className="cursor-pointer border-t border-line align-top hover:bg-canvas"
              onClick={() => navigate(`/report/${item.public_id}`)}
            >
              <td className="px-3 py-2 whitespace-nowrap">
                <a
                  href={`/report/${item.public_id}`}
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    navigate(`/report/${item.public_id}`);
                  }}
                >
                  {formatDateTime(item.submitted_at)}
                </a>
              </td>
              <td className="px-3 py-2">
                {item.filename ? (
                  <span className="font-mono">{item.filename}</span>
                ) : (
                  <span className="text-muted">(pasted)</span>
                )}
                <span className="block text-xs text-muted">
                  {LANGUAGE_LABEL[item.language] ?? item.language}
                </span>
              </td>
              <td className="px-3 py-2">{item.line_count}</td>
              <td className="px-3 py-2">
                {item.overall_risk_level ? (
                  <SeverityBadge level={item.overall_risk_level} prefix="" />
                ) : (
                  <span className="text-muted">{titleCase(item.status)}</span>
                )}
              </td>
              <td className="px-3 py-2">
                {item.overall_confidence ? (
                  <ConfidenceBadge level={item.overall_confidence} prefix="" />
                ) : (
                  "—"
                )}
              </td>
              <td className="px-3 py-2">
                {item.human_review_advised == null ? "—" : item.human_review_advised ? "Yes" : "No"}
              </td>
              <td className="max-w-xs px-3 py-2 text-muted">{item.purpose_summary_preview ?? "—"}</td>
              <td className="px-3 py-2">
                <button
                  type="button"
                  className="btn-link text-red-800"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(item);
                  }}
                  aria-label={`Delete the analysis from ${formatDateTime(item.submitted_at)}`}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
