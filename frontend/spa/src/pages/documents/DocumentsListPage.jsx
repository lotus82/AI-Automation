import { BookOpen, Pencil, Plus, RefreshCcw, Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import api from "../../api/client.js";
import { useAuthStore } from "../../store/authStore.js";
import { PAGE_SHELL, PAGE_TEXT } from "../../styles/pageLayout.js";
import { formatDateTimeRu } from "../../utils/dateTimeFormat.js";

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

export function DocumentsListPage() {
  const user = useAuthStore((s) => s.user);
  const role = user?.role;
  const canAccess = role === "super_admin" || role === "org_admin" || role === "director";

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [createTitle, setCreateTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [uploadTargetId, setUploadTargetId] = useState(null);
  /** Прогресс отправки файла на сервер (0–100), null — загрузки нет */
  const [uploadProgress, setUploadProgress] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get("/documents");
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
    const title = createTitle.trim();
    if (!title) return;
    setCreating(true);
    setError("");
    try {
      const { data } = await api.post("/documents", { title });
      setShowCreate(false);
      setCreateTitle("");
      setRows((prev) => [data, ...prev]);
    } catch (err) {
      setError(formatApiDetail(err?.response?.data?.detail) || err?.message || String(err));
    } finally {
      setCreating(false);
    }
  };

  const onDelete = async (id, title) => {
    if (!window.confirm(`Удалить документ «${title}» вместе со всеми узлами?`)) return;
    setDeletingId(id);
    setError("");
    try {
      await api.delete(`/documents/${id}`);
      setRows((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      setError(formatApiDetail(err?.response?.data?.detail) || err?.message || String(err));
    } finally {
      setDeletingId(null);
    }
  };

  const onPickUpload = (documentId) => {
    setUploadTargetId(documentId);
    const input = document.getElementById("documents-txt-upload");
    if (input) input.click();
  };

  const onUploadFile = async (e) => {
    const file = e.target.files?.[0];
    const target = uploadTargetId;
    e.target.value = "";
    setUploadTargetId(null);
    if (!file || !target) return;
    if (!file.name.toLowerCase().endsWith(".txt")) {
      setError("Выберите файл с расширением .txt");
      return;
    }
    setError("");
    setUploadProgress(0);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api.post(`/documents/${target}/upload`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (evt) => {
          if (evt.total && evt.total > 0) {
            setUploadProgress(Math.min(100, Math.round((100 * evt.loaded) / evt.total)));
          }
        },
      });
      setUploadProgress(100);
      await load();
    } catch (err) {
      setError(formatApiDetail(err?.response?.data?.detail) || err?.message || String(err));
    } finally {
      setUploadProgress(null);
    }
  };

  return (
    <div className={`${PAGE_SHELL} ${PAGE_TEXT} px-4 py-6 sm:px-6`}>
      <input
        id="documents-txt-upload"
        type="file"
        accept=".txt,text/plain"
        className="hidden"
        onChange={onUploadFile}
      />

      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-600/20 text-violet-300">
            <BookOpen className="h-5 w-5" strokeWidth={1.75} aria-hidden />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-white">Читатель</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-60"
          >
            <RefreshCcw className="h-3.5 w-3.5" aria-hidden />
            Обновить
          </button>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden />
            Создать документ
          </button>
        </div>
      </header>

      {uploadProgress !== null ? (
        <div className="mb-4 rounded-lg border border-slate-600 bg-slate-900/80 p-3">
          <div className="mb-1.5 text-xs font-medium text-slate-300">Загрузка файла на сервер…</div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full bg-emerald-500 transition-[width] duration-150 ease-out"
              style={{ width: `${uploadProgress}%` }}
              role="progressbar"
              aria-valuenow={uploadProgress}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
          <div className="mt-1 text-[11px] text-slate-500">{uploadProgress}%</div>
        </div>
      ) : null}

      {error ? (
        <div className="mb-4 rounded-lg border border-red-600/40 bg-red-600/10 p-3 text-sm text-red-200">{error}</div>
      ) : null}

      {showCreate ? (
        <form
          onSubmit={onCreate}
          className="mb-6 rounded-lg border border-slate-700 bg-slate-900/50 p-4"
        >
          <div className="text-sm font-medium text-slate-200">Новый документ</div>
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <label className="block min-w-[200px] flex-1 text-xs text-slate-400">
              Название
              <input
                type="text"
                value={createTitle}
                onChange={(e) => setCreateTitle(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                placeholder="Например, Библия"
                maxLength={512}
                required
              />
            </label>
            <button
              type="submit"
              disabled={creating}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
            >
              {creating ? "Создание…" : "Создать"}
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
            >
              Отмена
            </button>
          </div>
        </form>
      ) : null}

      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/40">
        <table className="min-w-full divide-y divide-slate-800 text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="px-4 py-3">Название</th>
              <th className="hidden px-4 py-3 sm:table-cell">Автор</th>
              <th className="px-4 py-3">Обновлён</th>
              <th className="px-4 py-3 text-right">Действия</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 text-slate-200">
            {loading ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                  Загрузка…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                  Документов пока нет. Создайте запись и загрузите .txt с разметкой{" "}
                  <code className="rounded bg-slate-800 px-1">== Книга ==</code>,{" "}
                  <code className="rounded bg-slate-800 px-1">=== Глава ===</code>.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.id} className="hover:bg-slate-800/40">
                  <td className="px-4 py-3 font-medium">{r.title}</td>
                  <td className="hidden px-4 py-3 text-slate-400 sm:table-cell">{r.author || "—"}</td>
                  <td className="px-4 py-3 text-slate-400">{formatDateTimeRu(r.updated_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap justify-end gap-2">
                      <button
                        type="button"
                        disabled={uploadProgress !== null}
                        onClick={() => onPickUpload(r.id)}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-600 bg-slate-800/80 px-2 py-1 text-xs text-slate-200 hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Upload className="h-3.5 w-3.5" aria-hidden />
                        Загрузить TXT
                      </button>
                      <Link
                        to={`/documents/${r.id}`}
                        className="inline-flex items-center gap-1 rounded-lg border border-emerald-700/50 bg-emerald-900/20 px-2 py-1 text-xs text-emerald-200 hover:bg-emerald-900/40"
                      >
                        <Pencil className="h-3.5 w-3.5" aria-hidden />
                        Редактор
                      </Link>
                      <button
                        type="button"
                        disabled={deletingId === r.id}
                        onClick={() => onDelete(r.id, r.title)}
                        className="inline-flex items-center gap-1 rounded-lg border border-red-800/50 bg-red-900/20 px-2 py-1 text-xs text-red-200 hover:bg-red-900/40 disabled:opacity-50"
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
    </div>
  );
}
