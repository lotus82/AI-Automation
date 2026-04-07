import { Outlet } from "react-router-dom";
import { Sidebar } from "../components/Sidebar.jsx";

/**
 * Общий каркас: боковое меню один раз, контент страниц — через Outlet.
 */
export function Layout() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-slate-800 bg-slate-900/40 px-6 py-3">
          <h1 className="text-sm font-medium text-slate-400">Корпоративная панель</h1>
        </header>
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
