import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { AccountSettingsDialog } from "./AccountSettingsDialog";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded px-2 py-1 text-sm font-medium no-underline hover:bg-white/10 hover:no-underline ${
    isActive ? "bg-white/15 text-white" : "text-gray-200"
  }`;

export function Header() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !menuRef.current?.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [menuOpen]);

  return (
    <header className="bg-brand text-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <Link
          to="/"
          className="mr-2 flex items-center gap-2 text-base font-bold text-white no-underline hover:no-underline"
        >
          <span aria-hidden="true" className="rounded bg-white/15 px-1.5 font-mono text-sm">
            {"{ }"}
          </span>
          <span>
            Explainable AI <span className="hidden sm:inline">Code Review Assistant</span>
            <span className="sm:hidden">Code Review</span>
          </span>
        </Link>
        <nav aria-label="Main" className="flex flex-wrap items-center gap-1">
          <NavLink to="/" end className={navClass}>
            Analyse
          </NavLink>
          {user && (
            <NavLink to="/history" className={navClass}>
              History
            </NavLink>
          )}
          <NavLink to="/about" className={navClass}>
            About
          </NavLink>
          {user?.role === "admin" && (
            <NavLink to="/admin/users" className={navClass}>
              Admin
            </NavLink>
          )}
        </nav>
        <div className="ml-auto flex items-center gap-2 text-sm">
          {!user ? (
            <>
              <Link to="/login" className="text-white">
                Log in
              </Link>
              <span aria-hidden="true" className="text-gray-400">
                |
              </span>
              <Link to="/register" className="text-white">
                Register
              </Link>
            </>
          ) : (
            <div className="relative" ref={menuRef}>
              <button
                type="button"
                className="rounded px-2 py-1 font-medium hover:bg-white/10"
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((o) => !o)}
              >
                {user.full_name} <span aria-hidden="true">▾</span>
              </button>
              {menuOpen && (
                <div
                  role="menu"
                  className="absolute right-0 z-40 mt-2 w-48 overflow-hidden rounded-md border border-line bg-surface text-ink shadow-lg"
                >
                  <button
                    role="menuitem"
                    type="button"
                    className="block w-full px-4 py-2 text-left text-sm hover:bg-canvas"
                    onClick={() => {
                      setMenuOpen(false);
                      navigate("/history");
                    }}
                  >
                    My history
                  </button>
                  <button
                    role="menuitem"
                    type="button"
                    className="block w-full px-4 py-2 text-left text-sm hover:bg-canvas"
                    onClick={() => {
                      setMenuOpen(false);
                      setSettingsOpen(true);
                    }}
                  >
                    Settings
                  </button>
                  <button
                    role="menuitem"
                    type="button"
                    className="block w-full border-t border-line px-4 py-2 text-left text-sm hover:bg-canvas"
                    onClick={async () => {
                      setMenuOpen(false);
                      await logout();
                      navigate("/");
                    }}
                  >
                    Log out
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      {settingsOpen && <AccountSettingsDialog onClose={() => setSettingsOpen(false)} />}
    </header>
  );
}
