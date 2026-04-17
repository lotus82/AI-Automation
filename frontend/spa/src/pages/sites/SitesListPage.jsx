import { Globe, Pencil, Plus, RefreshCcw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import api from "../../api/client.js";
import { useAuthStore } from "../../store/authStore.js";
import { PAGE_SHELL, PAGE_TEXT } from "../../styles/pageLayout.js";
import { formatDateTimeRu } from "../../utils/dateTimeFormat.js";

/** FastAPI detail → человеко-читаемая строка. */
function formatApiDetail(d) {
  if (d == null) return "";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d
      .map((item) => (typeof item === "string" ? item : item?.msg ? String(item.msg) : JSON.stringify(item)))
      .filter(Boolean)
      .join("; ");
  }
  if (typeof d === "object") return d.message ? String(d.message) : JSON.stringify(d);
  return String(d);
}

/**
 * Список сайтов организации. Доступ: super_admin, org_admin, director.
 * Всё изолировано по текущей организации (интерсептор добавит organization_id).
 */
export function SitesListPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const role = user?.role;
  const canAccess = role === "super_admin" || role === "org_admin" || role === "director";

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState("");
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get("/sites");
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (canAccess) load();
  }, [canAccess, load]);

  if (!user) return null;
  if (!canAccess) return <Navigate to="/scenarios/qa-analytics" replace />;

  const onCreate = async (e) => {
    e.preventDefault();
    const name = createName.trim();
    if (!name) return;
    setCreating(true);
    setError("");
    try {
      const { data } = await api.post("/sites", { name });
      setShowCreate(false);
      setCreateName("");
      navigate(`/sites/${data.id}`);
    } catch (err) {
      setError(formatApiDetail(err?.response?.data?.detail) || err?.message || String(err));
    } finally {
      setCreating(false);
    }
  };

  const onDelete = async (id, name) => {
    if (!window.confirm(`Удалить сайт «${name}» вместе со всеми страницами?`)) return;
    setDeletingId(id);
    setError("");
    try {
      await api.delete(`/sites/${id}`);
      setRows((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      setError(formatApiDetail(err?.response?.data?.detail) || err?.message || String(err));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className={`${PAGE_SHELL} ${PAGE_TEXT} px-4 py-6 sm:px-6`}>
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-600/20 text-sky-300">
            <Globe className="h-5 w-5" strokeWidth={1.75} aria-hidden />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-white">Сайты</h1>
            <p className="text-sm text-slate-400">
              Контент для клиентского Mini App. Многостраничные разделы с общими настройками.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-60"
          >
            <RefreshCcw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} aria-hidden />
            Обновить
          </button>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden />
            Создать сайт
          </button>
        </div>
      </header>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-600/40 bg-red-600/10 p-3 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      <section className="rounded-2xl border border-slate-800 bg-slate-900/70">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-800 text-sm">
            <thead className="bg-slate-900/60 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Название</th>
                <th className="px-4 py-2 text-left font-medium">Заголовок</th>
                <th className="px-4 py-2 text-left font-medium">Цвет</th>
                <th className="px-4 py-2 text-left font-medium">Обновлён</th>
                <th className="px-4 py-2 text-right font-medium">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td className="px-4 py-4 text-slate-400" colSpan={5}>
                    Загрузка…
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-center text-slate-500" colSpan={5}>
                    Ещё нет сайтов. Нажмите «Создать сайт», чтобы начать.
                  </td>
                </tr>
              ) : (
                rows.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-800/40">
                    <td className="px-4 py-2 font-medium text-slate-100">{s.name}</td>
                    <td className="px-4 py-2 text-slate-300">
                      {s.title || <span className="text-slate-500">—</span>}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <span
                          className="inline-block h-4 w-4 rounded-full ring-1 ring-slate-600"
                          style={{ backgroundColor: s.theme_color || "#000" }}
                          aria-hidden
                        />
                        <span className="font-mono text-xs text-slate-400">{s.theme_color}</span>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-slate-400">{formatDateTimeRu(s.updated_at)}</td>
                    <td className="px-4 py-2">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => navigate(`/sites/${s.id}`)}
                          className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/70 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
                          title="Редактировать"
                        >
                          <Pencil className="h-3.5 w-3.5" aria-hidden />
                          Редактировать
                        </button>
                        <button
                          type="button"
                          onClick={() => onDelete(s.id, s.name)}
                          disabled={deletingId === s.id}
                          className="inline-flex items-center gap-1 rounded-lg border border-red-700/60 bg-red-900/30 px-2.5 py-1.5 text-xs font-medium text-red-200 hover:bg-red-900/60 disabled:opacity-60"
                          title="Удалить"
                        >
                          <Trash2 className="h-3.5 w-3.5" aria-hidden />
                          Удалить
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {showCreate ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm"
          role="presentation"
          onClick={() => !creating && setShowCreate(false)}
        >
          <form
            onSubmit={onCreate}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl"
          >
            <h2 className="text-base font-semibold text-white">Новый сайт</h2>
            <p className="mt-1 text-xs text-slate-400">
              Внутреннее название отображается только в админ-панели. Заголовок и контент настроите в
              конструкторе.
            </p>
            <label className="mt-4 block text-xs font-medium text-slate-300">
              Внутреннее название
              <input
                autoFocus
                type="text"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                maxLength={255}
                placeholder="Сайт Mini App"
                className="mt-1 block w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-emerald-500 focus:outline-none"
                required
              />
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                disabled={creating}
                className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-60"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={creating || !createName.trim()}
                className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
              >
                {creating ? "Создание…" : "Создать"}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
