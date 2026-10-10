import { NavLink } from "react-router-dom";

const cls = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm font-semibold no-underline hover:no-underline ${
    isActive ? "bg-brand text-white" : "text-ink hover:bg-surface"
  }`;

export function AdminNav() {
  return (
    <nav
      aria-label="Administration"
      className="flex flex-wrap gap-2 rounded-lg border border-line bg-canvas p-1"
    >
      <NavLink to="/admin/users" className={cls}>
        Users
      </NavLink>
      <NavLink to="/admin/stats" className={cls}>
        Usage statistics
      </NavLink>
      <NavLink to="/admin/settings" className={cls}>
        Analysis settings
      </NavLink>
    </nav>
  );
}
