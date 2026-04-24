import { useCallback, useEffect, useState } from "react";
import { Plus, RefreshCcw, Store } from "lucide-react";
import { IconDeleteButton, IconEditLink } from "../components/ui/IconActionButtons.jsx";
import api from "../api/client.js";
import {
  PAGE_HEADER_BETWEEN,
  PAGE_H1,
  PAGE_TEXT,
  PAGE_TITLE_ICON,
} from "../styles/pageLayout.js";
import { formatDateTimeRu } from "../utils/dateTimeFormat.js";

function formatApiDetail(err) {
  const det = err?.response?.data?.detail;
  if (typeof det === "string") return det;
  if (Array.isArray(det)) return det.map((x) => x?.msg ?? x).join("; ");
  if (det != null) return JSON.stringify(det);
  return err?.message ?? String(err);
}

const pressable =
  "transition duration-100 ease-out select-none active:scale-[0.97] active:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/70 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950";
const pressableSub = `${pressable} hover:bg-slate-800/80`;
const pressablePri = `${pressable} shadow-sm active:shadow-inner`;

export function ShopsPage() {
  const [shops, setShops] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [nName, setNName] = useState("");
  const [nDesc, setNDesc] = useState("");
  const [nSlug, setNSlug] = useState("");

  const load = useCallback(async () => {
    setMsg("");
    try {
      const { data } = await api.get("/shops/organization");
      setShops(data ?? []);
    } catch (e) {
      setMsg(formatApiDetail(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onCreate = async (e) => {
    e.preventDefault();
    const name = nName.trim();
    if (!name) {
      setMsg("Укажите название магазина.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      await api.post("/shops/organization", {
        name,
        description: nDesc.trim(),
        slug: nSlug.trim() || null,
      });
      setCreateOpen(false);
      setNName("");
      setNDesc("");
      setNSlug("");
      await load();
    } catch (err) {
      setMsg(formatApiDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const onDelete = async (id, shopName) => {
    if (!window.confirm(`Удалить магазин «${shopName}» и связанные данные?`)) return;
    setBusy(true);
    setMsg("");
    try {
      await api.delete(`/shops/${id}`);
      await load();
    } catch (err) {
      setMsg(formatApiDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`w-full min-w-0 space-y-6 ${PAGE_TEXT}`}>
      <header className={PAGE_HEADER_BETWEEN}>
        <div className="flex items-center gap-3">
          <Store className={PAGE_TITLE_ICON} strokeWidth={1.5} aria-hidden />
          <h1 className={PAGE_H1}>Магазины</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-60"
          >
            <RefreshCcw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} aria-hidden />
            Обновить
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setCreateOpen(true);
              setMsg("");
            }}
            className={`inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 ${pressablePri}`}
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
            Добавить
          </button>
        </div>
      </header>

      {msg ? (
        <p className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-300">{msg}</p>
      ) : null}

      <section className="rounded-2xl border border-slate-800 bg-slate-900/70">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] divide-y divide-slate-800 text-left text-sm">
            <thead className="bg-slate-900/60 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Название</th>
                <th className="px-4 py-3 font-medium">Slug</th>
                <th className="px-4 py-3 font-medium">Обновлён</th>
                <th className="w-40 px-4 py-3 text-right font-medium">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-200">
            {loading ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                  Загрузка…
                </td>
              </tr>
            ) : shops.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                  Магазинов пока нет. Нажмите «Добавить».
                </td>
              </tr>
            ) : (
              shops.map((s) => (
                <tr key={s.id} className="hover:bg-slate-800/40">
                  <td className="px-4 py-3 font-medium text-slate-100">{s.name}</td>
                  <td className="px-4 py-3 text-slate-400">
                    <code className="text-xs text-emerald-200/80">/{s.slug}</code>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{formatDateTimeRu(s.updated_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex flex-wrap items-center justify-end gap-1">
                      <IconEditLink to={`/shops/${s.id}/edit`} className={pressableSub} />
                      <IconDeleteButton
                        disabled={busy}
                        title="Удалить магазин"
                        className={pressableSub}
                        onClick={() => onDelete(s.id, s.name)}
                      />
                    </div>
                  </td>
                </tr>
              ))
            )}
            </tbody>
          </table>
        </div>
      </section>

      {createOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="shop-create-title"
        >
          <form
            className="w-full max-w-md space-y-4 rounded-xl border border-slate-600 bg-slate-900 p-6 shadow-2xl"
            onSubmit={onCreate}
          >
            <h2 id="shop-create-title" className="text-lg font-semibold text-white">
              Новый магазин
            </h2>
            <label className="block text-xs text-slate-400">
              Название
              <input
                className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                value={nName}
                onChange={(e) => setNName(e.target.value)}
                autoFocus
                required
              />
            </label>
            <label className="block text-xs text-slate-400">
              Описание
              <textarea
                className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                rows={3}
                value={nDesc}
                onChange={(e) => setNDesc(e.target.value)}
              />
            </label>
            <label className="block text-xs text-slate-400">
              Slug (латиница, опционально)
              <input
                className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                value={nSlug}
                onChange={(e) => setNSlug(e.target.value.toLowerCase())}
                placeholder="auto"
              />
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                className={`rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-300 ${pressableSub}`}
                onClick={() => setCreateOpen(false)}
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={busy}
                className={`rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50 ${pressablePri}`}
              >
                Создать
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
