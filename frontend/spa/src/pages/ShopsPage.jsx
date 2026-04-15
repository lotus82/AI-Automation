import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Pencil, Plus, Store, Trash2 } from "lucide-react";
import api from "../api/client.js";

function formatApiDetail(err) {
  const det = err?.response?.data?.detail;
  if (typeof det === "string") return det;
  if (Array.isArray(det)) return det.map((x) => x?.msg ?? x).join("; ");
  if (det != null) return JSON.stringify(det);
  return err?.message ?? String(err);
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
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
    <div className="w-full min-w-0 space-y-6 pb-10 text-slate-100">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-white">
            <Store className="h-8 w-8 shrink-0 text-amber-400/90" strokeWidth={1.75} aria-hidden />
            Магазины
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Список витрин вашей организации. Редактирование каталога и страниц — в конструкторе магазина.
          </p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setCreateOpen(true);
            setMsg("");
          }}
          className={`inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 ${pressablePri}`}
        >
          <Plus className="h-4 w-4" strokeWidth={2} aria-hidden />
          Создать магазин
        </button>
      </div>

      {msg ? (
        <p className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-300">{msg}</p>
      ) : null}

      <div className="overflow-x-auto rounded-xl border border-slate-700/80 bg-slate-900/40">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-slate-700 bg-slate-900/60 text-xs uppercase text-slate-400">
            <tr>
              <th className="px-4 py-3">Название</th>
              <th className="px-4 py-3">Slug</th>
              <th className="px-4 py-3">Обновлён</th>
              <th className="px-4 py-3 w-40">Действия</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                  Загрузка…
                </td>
              </tr>
            ) : shops.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                  Магазинов пока нет. Нажмите «Создать магазин».
                </td>
              </tr>
            ) : (
              shops.map((s) => (
                <tr key={s.id} className="border-t border-slate-800">
                  <td className="px-4 py-3 font-medium text-slate-100">{s.name}</td>
                  <td className="px-4 py-3 text-slate-400">
                    <code className="text-xs text-emerald-200/80">/{s.slug}</code>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{formatDate(s.updated_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      <Link
                        to={`/shops/${s.id}/edit`}
                        className={`inline-flex items-center gap-1 rounded border border-slate-600 px-2 py-1 text-xs text-slate-200 ${pressableSub}`}
                      >
                        <Pencil className="h-3.5 w-3.5" aria-hidden />
                        Редактировать
                      </Link>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => onDelete(s.id, s.name)}
                        className={`inline-flex items-center gap-1 rounded border border-red-900/60 px-2 py-1 text-xs text-red-300 disabled:opacity-50 ${pressableSub}`}
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
