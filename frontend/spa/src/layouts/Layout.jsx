import { Menu } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import api from "../api/client.js";
import { Sidebar } from "../components/Sidebar.jsx";
import { SidebarMobileDrawer } from "../components/layout/Sidebar.jsx";
import { PAGE_SHELL, PAGE_TEXT } from "../styles/pageLayout.js";
import { useAuthStore } from "../store/authStore.js";

/**
 * Общий каркас: боковое меню один раз, контент страниц — через Outlet.
 */
export function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clearAuth);

  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);
  const [curPw, setCurPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwMsg, setPwMsg] = useState("");

  const logout = () => {
    clearAuth();
    navigate("/login", { replace: true });
  };

  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKey = (e) => {
      if (e.key === "Escape") setMobileNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileNavOpen]);

  const changePassword = async (e) => {
    e.preventDefault();
    setPwMsg("");
    try {
      await api.patch("/auth/me/password", {
        current_password: curPw,
        new_password: newPw,
      });
      setPwMsg("Пароль обновлён.");
      setCurPw("");
      setNewPw("");
    } catch (err) {
      const d = err?.response?.data?.detail;
      setPwMsg(typeof d === "string" ? d : "Ошибка");
    }
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <SidebarMobileDrawer open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-slate-800 bg-slate-900/40 px-3 py-3 sm:px-4 md:px-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-center gap-2 sm:gap-3">
              <button
                type="button"
                className="inline-flex shrink-0 rounded-lg border border-slate-600 p-2 text-slate-200 hover:bg-slate-800 md:hidden"
                aria-expanded={mobileNavOpen}
                aria-controls="mobile-nav-drawer"
                aria-label="Открыть меню"
                onClick={() => setMobileNavOpen(true)}
              >
                <Menu className="h-5 w-5" strokeWidth={2} aria-hidden />
              </button>
              <div className="min-w-0 md:hidden">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Lotus AI</div>
                <h1 className="truncate text-sm font-medium text-slate-300">Корпоративная панель</h1>
              </div>
              <h1 className="hidden text-sm font-medium text-slate-400 md:block">Корпоративная панель</h1>
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm sm:justify-end">
              <span className="max-w-full truncate text-slate-500">
                {user?.display_name || user?.username}
                {user?.organization_name ? (
                  <span className="text-slate-600"> · {user.organization_name}</span>
                ) : null}
              </span>
              <button
                type="button"
                className="shrink-0 text-sky-400 hover:text-sky-300"
                onClick={() => {
                  setPwOpen(true);
                  setPwMsg("");
                }}
              >
                Сменить пароль
              </button>
              <Link to="/" className="shrink-0 text-slate-500 hover:text-slate-300">
                О платформе
              </Link>
              <button
                type="button"
                className="shrink-0 rounded-lg border border-slate-600 px-3 py-1 text-slate-300 hover:bg-slate-800"
                onClick={logout}
              >
                Выйти
              </button>
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-3 sm:p-4 md:p-6">
          <div className={`${PAGE_SHELL} ${PAGE_TEXT}`}>
            <Outlet />
          </div>
        </main>
      </div>

      {pwOpen ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 bg-black/60"
            aria-label="Закрыть"
            onClick={() => setPwOpen(false)}
          />
          <div
            className="fixed left-1/2 top-1/2 z-50 w-[min(100%-2rem,24rem)] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-slate-600 bg-slate-900 p-5 shadow-xl"
            role="dialog"
            aria-modal="true"
          >
            <h2 className="text-lg font-semibold text-white">Смена пароля</h2>
            <form className="mt-4 space-y-3" onSubmit={changePassword}>
              {pwMsg ? <p className="text-sm text-emerald-400">{pwMsg}</p> : null}
              <div>
                <label className="mb-1 block text-xs text-slate-400">Текущий пароль</label>
                <input
                  type="password"
                  required
                  className="w-full rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
                  value={curPw}
                  onChange={(e) => setCurPw(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-400">Новый пароль (мин. 6)</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  className="w-full rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                />
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500"
                >
                  Сохранить
                </button>
                <button
                  type="button"
                  className="rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-300"
                  onClick={() => setPwOpen(false)}
                >
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </>
      ) : null}
    </div>
  );
}

