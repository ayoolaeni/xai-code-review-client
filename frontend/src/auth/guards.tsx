import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { PageSkeleton } from "../components/Skeleton";
import { useAuth } from "./AuthContext";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <PageSkeleton />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <PageSkeleton />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (user.role !== "admin") {
    return (
      <div className="mx-auto max-w-xl rounded-lg border border-line bg-surface p-6" role="alert">
        <h1 className="text-lg font-semibold">Administrator access required</h1>
        <p className="mt-2 text-muted">This page is only available to administrators.</p>
      </div>
    );
  }
  return <>{children}</>;
}

export function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <PageSkeleton />;
  if (user) return <Navigate to="/" replace />;
  return <>{children}</>;
}
