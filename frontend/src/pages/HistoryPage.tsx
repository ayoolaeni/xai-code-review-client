import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api/client";
import type { HistoryItem } from "../api/types";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { EmptyState, ErrorAlert } from "../components/Feedback";
import { HistoryTable } from "../components/HistoryTable";
import { Pagination } from "../components/Pagination";
import { TableSkeleton } from "../components/Skeleton";
import { useToast } from "../components/Toast";

const PAGE_SIZE = 20;

export function HistoryPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [language, setLanguage] = useState("");
  const [toDelete, setToDelete] = useState<HistoryItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const queryClient = useQueryClient();
  const toast = useToast();

  useEffect(() => {
    document.title = "History · Explainable AI Code Review Assistant";
  }, []);

  // Debounce the search box.
  useEffect(() => {
    const id = window.setTimeout(() => {
      setQ(search.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(id);
  }, [search]);

  const history = useQuery({
    queryKey: ["history", page, q, language],
    queryFn: () => api.history({ page, page_size: PAGE_SIZE, q, language }),
    placeholderData: keepPreviousData,
  });

  async function confirmDelete() {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await api.deleteAnalysis(toDelete.public_id);
      toast("The analysis was deleted.");
      await queryClient.invalidateQueries({ queryKey: ["history"] });
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "The analysis could not be deleted.", "error");
    } finally {
      setDeleting(false);
      setToDelete(null);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1>My analyses</h1>
        <p className="mt-1 text-muted">Reopen or delete your past code reviews.</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-[1fr_200px]">
        <div>
          <label htmlFor="history-search" className="label">
            Search purpose or file name
          </label>
          <input
            id="history-search"
            type="search"
            className="input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="e.g. login, invoice.py"
          />
        </div>
        <div>
          <label htmlFor="history-language" className="label">
            Language
          </label>
          <select
            id="history-language"
            className="input"
            value={language}
            onChange={(e) => {
              setLanguage(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All languages</option>
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="java">Java</option>
          </select>
        </div>
      </div>

      {history.isLoading ? (
        <TableSkeleton />
      ) : history.isError ? (
        <ErrorAlert message={(history.error as Error).message} onRetry={() => history.refetch()} />
      ) : history.data && history.data.items.length === 0 ? (
        <EmptyState title={q || language ? "No analyses match your search." : "You have no analyses yet."}>
          {!q && !language && <Link to="/">Analyse some code</Link>}
        </EmptyState>
      ) : (
        history.data && (
          <>
            <p className="text-sm text-muted">{history.data.total} analysis(es)</p>
            <HistoryTable items={history.data.items} onDelete={setToDelete} />
            <Pagination page={page} pageSize={PAGE_SIZE} total={history.data.total} onChange={setPage} />
          </>
        )
      )}

      <ConfirmDialog
        open={toDelete !== null}
        title="Delete this analysis?"
        message="The report, its findings and any stored code will be permanently deleted."
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
        busy={deleting}
      />
    </div>
  );
}
