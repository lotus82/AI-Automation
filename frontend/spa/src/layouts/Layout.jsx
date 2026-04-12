import { useState } from "react";
import { Link, Outlet, useNavigate } from "react-router-dom";
import api from "../api/client.js";
import { Sidebar } from "../components/Sidebar.jsx";
import { PAGE_SHELL, PAGE_TEXT } from "../styles/pageLayout.js";
import { useAuthStore } from "../store/authStore.js";

/**
 * Общий каркас: боковое меню один раз, контент страниц — через Outlet.
 */
export function Layout() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clearAuth);

  const [pwOpen, setPwOpen] = useState(false);
  const [curPw, setCurPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwMsg, setPwMsg] = useState("");

  const logout = () => {
    clearAuth();
    navigate("/login", { replace: true });
  };

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
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900/40 px-6 py-3">
          <h1 className="text-sm font-medium text-slate-400">Корпоративная панель</h1>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="text-slate-500">
              {user?.display_name || user?.username}
              {user?.organization_name ? (
                <span className="text-slate-600"> · {user.organization_name}</span>
              ) : null}
            </span>
            <button
              type="button"
              className="text-sky-400 hover:text-sky-300"
              onClick={() => {
                setPwOpen(true);
                setPwMsg("");
              }}
            >
              Сменить пароль
            </button>
            <Link to="/" className="text-slate-500 hover:text-slate-300">
              О платформе
            </Link>
            <button
              type="button"
              className="rounded-lg border border-slate-600 px-3 py-1 text-slate-300 hover:bg-slate-800"
              onClick={logout}
            >
              Выйти
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-6">
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

