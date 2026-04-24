import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import api from "../api/client.js";
import { useAuthStore } from "../store/authStore.js";
import { PAGE_H1, PAGE_TEXT } from "../styles/pageLayout.js";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const from = (() => {
    if (location.state?.from) return location.state.from;
    const sp = new URLSearchParams(location.search);
    if (sp.get("DOMAIN") || sp.get("domain") || sp.get("APP_SID") || sp.get("app_sid")) {
      return `/scenarios/qa-analytics${location.search}`;
    }
    return "/scenarios/qa-analytics";
  })();

  const setAuth = useAuthStore((s) => s.setAuth);
  const setUser = useAuthStore((s) => s.setUser);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data: loginData } = await api.post("/auth/login", {
        username: username.trim(),
        password,
      });
      const token = loginData?.access_token;
      if (!token) {
        setError("Некорректный ответ сервера");
        return;
      }
      setAuth(token, null);
      const { data: me } = await api.get("/auth/me");
      setUser(me);
      navigate(from, { replace: true });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Не удалось войти. Проверьте логин и пароль.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-950 px-4 py-12">
      <div className="w-full max-w-md rounded-2xl border border-slate-700/80 bg-slate-900/60 p-8 shadow-xl backdrop-blur-sm">
        <h1 className="text-center text-2xl font-bold text-white">Вход в панель</h1>
        <p className="mt-2 text-center text-sm text-slate-400">Lotus AI — корпоративный доступ</p>

        <form className="mt-8 space-y-4" onSubmit={onSubmit}>
          {error ? (
            <p className="rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300" role="alert">
              {error}
            </p>
          ) : null}
          <div>
            <label htmlFor="login-user" className="mb-1 block text-xs font-medium text-slate-400">
              Логин
            </label>
            <input
              id="login-user"
              autoComplete="username"
              className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div>
            <label htmlFor="login-pass" className="mb-1 block text-xs font-medium text-slate-400">
              Пароль
            </label>
            <input
              id="login-pass"
              type="password"
              autoComplete="current-password"
              className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-emerald-600 py-2.5 text-sm font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-50"
          >
            {loading ? "Вход…" : "Войти"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-500">
          <Link to="/" className="text-emerald-500 hover:text-emerald-400">
            На главную
          </Link>
        </p>
      </div>
    </div>
  );
}
