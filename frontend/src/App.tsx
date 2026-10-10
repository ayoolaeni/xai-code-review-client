import { Route, Routes } from "react-router-dom";

import { RedirectIfAuthed, RequireAdmin, RequireAuth } from "./auth/guards";
import { Header } from "./components/Header";
import { AboutPage } from "./pages/AboutPage";
import { AdminSettingsPage } from "./pages/admin/AdminSettingsPage";
import { AdminStatsPage } from "./pages/admin/AdminStatsPage";
import { AdminUsersPage } from "./pages/admin/AdminUsersPage";
import { AnalysePage } from "./pages/AnalysePage";
import { HistoryPage } from "./pages/HistoryPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ReportPage } from "./pages/ReportPage";

export function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <Header />
      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        <Routes>
          <Route path="/" element={<AnalysePage />} />
          <Route path="/report/:publicId" element={<ReportPage />} />
          <Route
            path="/history"
            element={
              <RequireAuth>
                <HistoryPage />
              </RequireAuth>
            }
          />
          <Route
            path="/login"
            element={
              <RedirectIfAuthed>
                <LoginPage />
              </RedirectIfAuthed>
            }
          />
          <Route
            path="/register"
            element={
              <RedirectIfAuthed>
                <RegisterPage />
              </RedirectIfAuthed>
            }
          />
          <Route path="/about" element={<AboutPage />} />
          <Route
            path="/admin/users"
            element={
              <RequireAdmin>
                <AdminUsersPage />
              </RequireAdmin>
            }
          />
          <Route
            path="/admin/stats"
            element={
              <RequireAdmin>
                <AdminStatsPage />
              </RequireAdmin>
            }
          />
          <Route
            path="/admin/settings"
            element={
              <RequireAdmin>
                <AdminSettingsPage />
              </RequireAdmin>
            }
          />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      <footer className="border-t border-line bg-surface py-4 text-center text-xs text-muted">
        Explainable AI Code Review Assistant · Submitted code is analysed as text and is never executed · AI
        output may be wrong — review before use.
      </footer>
    </div>
  );
}
