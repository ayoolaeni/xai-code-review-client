import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, ApiError } from "../../api/client";
import type { AdminUser } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { AdminNav } from "../../components/admin/AdminNav";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState, ErrorAlert } from "../../components/Feedback";
import { Pagination } from "../../components/Pagination";
import { TableSkeleton } from "../../components/Skeleton";
import { useToast } from "../../components/Toast";
import { formatDateTime } from "../../utils/format";

export function AdminUsersPage() {
  const { user: me } = useAuth();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [toDelete, setToDelete] = useState<AdminUser | null>(null);
  const [busy, setBusy] = useState(false);
  const queryClient = useQueryClient();
  const toast = useToast();

  useEffect(() => {
    document.title = "Users · Administration";
  }, []);
  useEffect(() => {
    const id = window.setTimeout(() => {
      setQ(search.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(id);
  }, [search]);

  const users = useQuery({
    queryKey: ["admin-users", page, q],
    queryFn: () => api.adminUsers(page, q),
    placeholderData: keepPreviousData,
  });

  async function update(u: AdminUser, body: { role?: "user" | "admin"; is_active?: boolean }) {
    try {
      await api.adminUpdateUser(u.user_id, body);
      toast(`${u.full_name} was updated.`);
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "The user could not be updated.", "error");
    }
  }

  async function remove() {
    if (!toDelete) return;
    setBusy(true);
    try {
      await api.adminDeleteUser(toDelete.user_id);
      toast(`${toDelete.full_name} and their data were deleted.`);
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "The user could not be deleted.", "error");
    } finally {
      setBusy(false);
      setToDelete(null);
    }
  }

  return (
    <div className="space-y-5">
      <h1>Administration</h1>
      <AdminNav />
      <div>
        <label htmlFor="user-search" className="label">
          Search by name or email
        </label>
        <input
          id="user-search"
          type="search"
          className="input max-w-md"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      {users.isLoading ? (
        <TableSkeleton />
      ) : users.isError ? (
        <ErrorAlert message={(users.error as Error).message} onRetry={() => users.refetch()} />
      ) : users.data && users.data.items.length === 0 ? (
        <EmptyState title="No users match your search." />
      ) : (
        users.data && (
          <>
            <div className="overflow-x-auto rounded-lg border border-line bg-surface">
              <table className="w-full min-w-[760px] text-left text-sm">
                <caption className="sr-only">User accounts</caption>
                <thead className="bg-canvas">
                  <tr>
                    <th scope="col" className="px-3 py-2">
                      Name
                    </th>
                    <th scope="col" className="px-3 py-2">
                      Email
                    </th>
                    <th scope="col" className="px-3 py-2">
                      Role
                    </th>
                    <th scope="col" className="px-3 py-2">
                      Active
                    </th>
                    <th scope="col" className="px-3 py-2">
                      Analyses
                    </th>
                    <th scope="col" className="px-3 py-2">
                      Registered
                    </th>
                    <th scope="col" className="px-3 py-2">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {users.data.items.map((u) => {
                    const self = u.user_id === me?.user_id;
                    return (
                      <tr key={u.user_id} className="border-t border-line">
                        <td className="px-3 py-2">
                          {u.full_name}
                          {self && <span className="ml-1 text-xs text-muted">(you)</span>}
                        </td>
                        <td className="px-3 py-2">{u.email}</td>
                        <td className="px-3 py-2">
                          <label className="sr-only" htmlFor={`role-${u.user_id}`}>
                            Role of {u.full_name}
                          </label>
                          <select
                            id={`role-${u.user_id}`}
                            className="input py-1"
                            value={u.role}
                            disabled={self}
                            onChange={(e) => update(u, { role: e.target.value as "user" | "admin" })}
                          >
                            <option value="user">User</option>
                            <option value="admin">Administrator</option>
                          </select>
                        </td>
                        <td className="px-3 py-2">
                          <label className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={u.is_active}
                              disabled={self}
                              onChange={(e) => update(u, { is_active: e.target.checked })}
                            />
                            <span>{u.is_active ? "Active" : "Deactivated"}</span>
                          </label>
                        </td>
                        <td className="px-3 py-2 tabular-nums">{u.analysis_count}</td>
                        <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(u.created_at)}</td>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            className="btn-link text-red-800"
                            disabled={self}
                            onClick={() => setToDelete(u)}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pagination
              page={page}
              pageSize={users.data.page_size}
              total={users.data.total}
              onChange={setPage}
            />
          </>
        )
      )}
      <ConfirmDialog
        open={toDelete !== null}
        title={`Delete ${toDelete?.full_name ?? "user"}?`}
        message="The account and all of its analyses, reports and feedback will be permanently deleted."
        onConfirm={remove}
        onCancel={() => setToDelete(null)}
        busy={busy}
      />
    </div>
  );
}
