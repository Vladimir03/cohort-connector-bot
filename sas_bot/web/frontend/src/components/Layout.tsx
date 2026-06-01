import { NavLink, Outlet } from "react-router-dom";
import { BarChart3, Users, Activity, Megaphone, LogOut } from "lucide-react";
import { cn } from "./ui";

const navItems = [
  { to: "/", label: "Dashboard", icon: BarChart3, end: true },
  { to: "/users", label: "Users", icon: Users },
  { to: "/events", label: "Events", icon: Activity },
  { to: "/broadcast", label: "Broadcast", icon: Megaphone },
];

export default function Layout() {
  return (
    <div className="min-h-screen flex">
      <aside className="w-56 shrink-0 border-r border-zinc-800 bg-zinc-950 flex flex-col">
        <div className="px-5 py-5 border-b border-zinc-800">
          <div className="text-sm font-semibold text-zinc-100">SAS Bot</div>
          <div className="text-xs text-zinc-500">Admin Dashboard</div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 px-3 py-2 rounded-md text-sm transition",
                  isActive
                    ? "bg-emerald-500/10 text-emerald-300"
                    : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-100",
                )
              }
            >
              <it.icon className="w-4 h-4" />
              {it.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-zinc-800">
          <button
            onClick={() => {
              // HTTP Basic logout trick: navigate with garbage credentials
              window.location.href = "/api/stats";
              setTimeout(() => (window.location.href = "/"), 200);
            }}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-100"
            title="Re-prompt HTTP Basic auth"
          >
            <LogOut className="w-4 h-4" /> Logout
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0">
        <header className="h-14 border-b border-zinc-800 flex items-center justify-between px-6">
          <div className="text-sm text-zinc-400">
            Signed in as <span className="text-zinc-100 font-medium">admin</span>
          </div>
        </header>
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
