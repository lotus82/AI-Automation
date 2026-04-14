import { useCallback, useEffect, useMemo, useState } from "react";
import { ShoppingBag } from "lucide-react";
import api from "../api/client.js";

const MESSENGERS = [
  { id: "max", label: "MAX" },
  { id: "telegram", label: "Telegram" },
  { id: "vk", label: "VK" },
];

const THEME_KEYS = [
  { key: "accent", label: "Акцент" },
  { key: "bg", label: "Фон" },
  { key: "card", label: "Карточка" },
  { key: "text", label: "Текст" },
  { key: "muted", label: "Второст." },
];

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

function emptyThemeState() {
  return {
    max: { accent: "", bg: "", card: "", text: "", muted: "" },
    telegram: { accent: "", bg: "", card: "", text: "", muted: "" },
    vk: { accent: "", bg: "", card: "", text: "", muted: "" },
  };
}

function themesToPatch(t) {
  const out = {};
  for (const m of MESSENGERS) {
    const row = t[m.id] || {};
    const o = {};
    for (const { key } of THEME_KEYS) {
      const v = (row[key] || "").trim();
      if (v) o[key] = v;
    }
    if (Object.keys(o).length) out[m.id] = o;
  }
  return { messenger_themes: Object.keys(out).length ? out : {} };
}

export function ShopsPage() {
  const [shops, setShops] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [products, setProducts] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [slug, setSlug] = useState("");
  const [themeState, setThemeState] = useState(emptyThemeState);
  const [sellerMax, setSellerMax] = useState("");
  const [sellerTg, setSellerTg] = useState("");
  const [sellerVk, setSellerVk] = useState("");
  const [busy, setBusy] = useState(false);

  const [pName, setPName] = useState("");
  const [pDesc, setPDesc] = useState("");
  const [pPrice, setPPrice] = useState("");
  const [pStock, setPStock] = useState("0");
  const [pSort, setPSort] = useState("0");

  const loadShops = useCallback(async () => {
    setMsg("");
    try {
      const { data } = await api.get("/shops");
      setShops(data ?? []);
    } catch (e) {
      setMsg(formatApiDetail(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadShops();
  }, [loadShops]);

  const loadDetail = async (id) => {
    if (!id) {
      setDetail(null);
      setProducts([]);
      return;
    }
    setMsg("");
    try {
      const [{ data: d }, { data: pr }] = await Promise.all([
        api.get(`/shops/${id}`),
        api.get(`/shops/${id}/products`),
      ]);
      setDetail(d);
      setProducts(pr ?? []);
      setName(d.name ?? "");
      setDescription(d.description ?? "");
      setSlug(d.slug ?? "");
      const next = emptyThemeState();
      const stored = d.messenger_themes || {};
      for (const m of MESSENGERS) {
        const row = stored[m.id];
        if (row && typeof row === "object") {
          for (const { key } of THEME_KEYS) {
            if (row[key]) next[m.id][key] = String(row[key]);
          }
        }
      }
      setThemeState(next);
      setSellerMax(d.seller_max_chat_id ?? "");
      setSellerTg(d.seller_telegram_chat_id ?? "");
      setSellerVk(d.seller_vk_peer_id ?? "");
    } catch (e) {
      setMsg(formatApiDetail(e));
    }
  };

  useEffect(() => {
    if (selectedId) loadDetail(selectedId);
  }, [selectedId]);

  const publicShopUrl = useMemo(() => {
    if (!detail?.slug) return "";
    const base = `${window.location.origin}/public/shop/${detail.slug}`;
    return base;
  }, [detail?.slug]);

  const onCreateShop = async (e) => {
    e.preventDefault();
    const n = name.trim();
    if (!n) {
      setMsg("Укажите название магазина.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      const body = {
        name: n,
        description: description.trim(),
        slug: slug.trim() || null,
        seller_max_chat_id: sellerMax.trim() || null,
        seller_telegram_chat_id: sellerTg.trim() || null,
        seller_vk_peer_id: sellerVk.trim() || null,
        ...themesToPatch(themeState),
      };
      const { data } = await api.post("/shops", body);
      setSelectedId(data.id);
      await loadShops();
      setMsg("Магазин создан.");
    } catch (err) {
      setMsg(formatApiDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const onSaveShop = async () => {
    if (!selectedId) return;
    setBusy(true);
    setMsg("");
    try {
      await api.patch(`/shops/${selectedId}`, {
        name: name.trim(),
        description: description.trim(),
        slug: slug.trim() || undefined,
        seller_max_chat_id: sellerMax.trim() || null,
        seller_telegram_chat_id: sellerTg.trim() || null,
        seller_vk_peer_id: sellerVk.trim() || null,
        ...themesToPatch(themeState),
      });
      await loadShops();
      await loadDetail(selectedId);
      setMsg("Сохранено.");
    } catch (err) {
      setMsg(formatApiDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const onDeleteShop = async () => {
    if (!selectedId || !window.confirm("Удалить магазин и все товары?")) return;
    setBusy(true);
    try {
      await api.delete(`/shops/${selectedId}`);
      setSelectedId(null);
      setDetail(null);
      await loadShops();
      setMsg("Удалено.");
    } catch (err) {
      setMsg(formatApiDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const onLogo = async (file) => {
    if (!selectedId || !file) return;
    const fd = new FormData();
    fd.append("file", file);
    setBusy(true);
    try {
      await api.post(`/shops/${selectedId}/logo`, fd);
      await loadDetail(selectedId);
      await loadShops();
    } catch (err) {
      setMsg(formatApiDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const addProduct = async (e) => {
    e.preventDefault();
    if (!selectedId) return;
    const price = pPrice.replace(",", ".").trim();
    if (!pName.trim() || !price) {
      setMsg("Товар: укажите название и цену.");
      return;
    }
    setBusy(true);
    try {
      await api.post(`/shops/${selectedId}/products`, {
        name: pName.trim(),
        description: pDesc.trim(),
        price,
        stock_quantity: Math.max(0, parseInt(pStock, 10) || 0),
        sort_order: parseInt(pSort, 10) || 0,
      });
      setPName("");
      setPDesc("");
      setPPrice("");
      setPStock("0");
      setPSort("0");
      await loadDetail(selectedId);
    } catch (err) {
      setMsg(formatApiDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const deleteProduct = async (pid) => {
    if (!selectedId || !window.confirm("Удалить товар?")) return;
    try {
      await api.delete(`/shops/${selectedId}/products/${pid}`);
      await loadDetail(selectedId);
    } catch (err) {
      setMsg(formatApiDetail(err));
    }
  };

  const uploadProductPhoto = async (pid, file) => {
    if (!selectedId || !file) return;
    const fd = new FormData();
    fd.append("file", file);
    setBusy(true);
    try {
      await api.post(`/shops/${selectedId}/products/${pid}/photo`, fd);
      await loadDetail(selectedId);
    } catch (err) {
      setMsg(formatApiDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const patchProductStock = async (pid, raw) => {
    const n = Math.max(0, parseInt(String(raw), 10) || 0);
    if (!selectedId) return;
    setBusy(true);
    try {
      await api.patch(`/shops/${selectedId}/products/${pid}`, { stock_quantity: n });
      await loadDetail(selectedId);
    } catch (err) {
      setMsg(formatApiDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const setThemeVal = (messenger, key, value) => {
    setThemeState((prev) => ({
      ...prev,
      [messenger]: { ...prev[messenger], [key]: value },
    }));
  };

  const newShopMode = !selectedId;

  return (
    <div className="w-full min-w-0 space-y-6 text-slate-100 pb-10">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-white">
          <ShoppingBag className="h-8 w-8 shrink-0 text-amber-400/90" strokeWidth={1.75} aria-hidden />
          Магазины
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Витрина для мини-приложений MAX, Telegram, VK. Публичная ссылка с темой под мессенджер и мобильную вёрстку.
        </p>
      </div>

      {msg ? (
        <p className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-300">{msg}</p>
      ) : null}

      <div className="grid gap-8 xl:grid-cols-[280px_1fr]">
        <aside className="space-y-3 rounded-xl border border-slate-700/80 bg-slate-900/40 p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-slate-200">Список</span>
            <button
              type="button"
              className={`rounded border border-slate-600 px-2 py-1 text-xs text-emerald-300 ${pressableSub}`}
              onClick={() => {
                setSelectedId(null);
                setDetail(null);
                setName("");
                setDescription("");
                setSlug("");
                setThemeState(emptyThemeState());
                setSellerMax("");
                setSellerTg("");
                setSellerVk("");
                setProducts([]);
              }}
            >
              + Новый
            </button>
          </div>
          {loading ? <p className="text-xs text-slate-500">Загрузка…</p> : null}
          <ul className="max-h-[50vh] space-y-1 overflow-y-auto">
            {shops.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(s.id)}
                  className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition ${
                    selectedId === s.id
                      ? "border-emerald-600/50 bg-emerald-950/30 text-white"
                      : "border-slate-700 bg-slate-950/50 text-slate-300 hover:border-slate-600"
                  } ${pressableSub}`}
                >
                  <span className="font-medium">{s.name}</span>
                  <span className="block text-xs text-slate-500">/{s.slug}</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <div className="min-w-0 space-y-6">
          <form
            className="space-y-4 rounded-xl border border-slate-700/80 bg-slate-900/50 p-5"
            onSubmit={newShopMode ? onCreateShop : (e) => e.preventDefault()}
          >
            <h2 className="text-lg font-semibold text-slate-200">{newShopMode ? "Новый магазин" : "Редактирование"}</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs text-slate-400">Название</label>
                <input
                  className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required={newShopMode}
                />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs text-slate-400">Описание</label>
                <textarea
                  className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-400">Slug в URL (латиница)</label>
                <input
                  className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value.toLowerCase())}
                  placeholder="my-store"
                />
              </div>
              {!newShopMode && detail ? (
                <div>
                  <label className="mb-1 block text-xs text-slate-400">Логотип</label>
                  <input
                    type="file"
                    accept="image/*"
                    className="block w-full text-xs text-slate-400"
                    onChange={(e) => onLogo(e.target.files?.[0])}
                  />
                </div>
              ) : null}
            </div>

            <div className="rounded-lg border border-slate-700 bg-slate-950/40 p-4">
              <h3 className="text-sm font-medium text-slate-200">Темы под мессенджеры</h3>
              <p className="mt-1 text-xs text-slate-500">Цвета (#rrggbb). Пустое — взять пресет по умолчанию для канала.</p>
              <div className="mt-3 grid gap-4 lg:grid-cols-3">
                {MESSENGERS.map((m) => (
                  <div key={m.id} className="rounded border border-slate-700 p-3">
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{m.label}</div>
                    {THEME_KEYS.map(({ key, label }) => (
                      <label key={key} className="mb-2 block text-xs">
                        <span className="text-slate-500">{label}</span>
                        <input
                          className="mt-0.5 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 font-mono text-xs text-white"
                          value={themeState[m.id][key]}
                          onChange={(e) => setThemeVal(m.id, key, e.target.value)}
                          placeholder="#hex"
                        />
                      </label>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-slate-700 bg-slate-950/40 p-4">
              <h3 className="text-sm font-medium text-slate-200">Уведомления продавцу о заказах</h3>
              <p className="mt-1 text-xs text-slate-500">
                Укажите ID чата/peer, куда бот отправит текст заказа для выбранного на витрине мессенджера. Для VK на сервере
                нужен VK_API_ACCESS_TOKEN (сообщество с правом messages).
              </p>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <label className="block text-xs">
                  <span className="text-slate-500">MAX — chat id продавца</span>
                  <input
                    className="mt-0.5 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1.5 text-sm text-white"
                    value={sellerMax}
                    onChange={(e) => setSellerMax(e.target.value)}
                    placeholder="например 12345"
                  />
                </label>
                <label className="block text-xs">
                  <span className="text-slate-500">Telegram — chat id</span>
                  <input
                    className="mt-0.5 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1.5 text-sm text-white"
                    value={sellerTg}
                    onChange={(e) => setSellerTg(e.target.value)}
                    placeholder="например 123456789"
                  />
                </label>
                <label className="block text-xs">
                  <span className="text-slate-500">VK — peer id</span>
                  <input
                    className="mt-0.5 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1.5 text-sm text-white"
                    value={sellerVk}
                    onChange={(e) => setSellerVk(e.target.value)}
                    placeholder="например 2000000001"
                  />
                </label>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {newShopMode ? (
                <button
                  type="submit"
                  disabled={busy}
                  className={`rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 ${pressablePri}`}
                >
                  Создать
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    disabled={busy}
                    className={`rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 ${pressablePri}`}
                    onClick={onSaveShop}
                  >
                    Сохранить
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    className={`rounded-lg border border-red-800 px-4 py-2 text-sm text-red-300 disabled:opacity-50 ${pressableSub}`}
                    onClick={onDeleteShop}
                  >
                    Удалить магазин
                  </button>
                </>
              )}
            </div>

            {!newShopMode && publicShopUrl ? (
              <div className="rounded-lg border border-slate-700 bg-slate-950/50 p-3 text-xs">
                <div className="font-medium text-slate-300">Публичные ссылки (для мини-приложений)</div>
                <p className="mt-2 text-slate-500">Базовая:</p>
                <code className="mt-1 block break-all text-emerald-200/90">{publicShopUrl}</code>
                <p className="mt-2 text-slate-500">С темой MAX / Telegram / VK:</p>
                {MESSENGERS.map((m) => (
                  <code key={m.id} className="mt-1 block break-all text-sky-200/80">
                    {publicShopUrl}?messenger={m.id}
                  </code>
                ))}
              </div>
            ) : null}
          </form>

          {!newShopMode && selectedId ? (
            <div className="space-y-4 rounded-xl border border-slate-700/80 bg-slate-900/40 p-5">
              <h3 className="text-lg font-semibold text-slate-200">Товары</h3>
              <form className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5" onSubmit={addProduct}>
                <input
                  className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
                  placeholder="Название"
                  value={pName}
                  onChange={(e) => setPName(e.target.value)}
                />
                <input
                  className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
                  placeholder="Цена"
                  value={pPrice}
                  onChange={(e) => setPPrice(e.target.value)}
                />
                <input
                  className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
                  placeholder="В наличии"
                  value={pStock}
                  onChange={(e) => setPStock(e.target.value)}
                  type="number"
                  min="0"
                />
                <input
                  className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
                  placeholder="Порядок"
                  value={pSort}
                  onChange={(e) => setPSort(e.target.value)}
                />
                <button
                  type="submit"
                  disabled={busy}
                  className={`rounded-lg bg-slate-700 px-3 py-1.5 text-sm text-white disabled:opacity-50 ${pressablePri}`}
                >
                  Добавить
                </button>
                <textarea
                  className="sm:col-span-2 lg:col-span-5 rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
                  placeholder="Описание товара"
                  rows={2}
                  value={pDesc}
                  onChange={(e) => setPDesc(e.target.value)}
                />
              </form>

              <div className="overflow-x-auto rounded-lg border border-slate-700">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead className="border-b border-slate-700 bg-slate-900/60 text-xs uppercase text-slate-400">
                    <tr>
                      <th className="px-3 py-2">Название</th>
                      <th className="px-3 py-2">Цена</th>
                      <th className="px-3 py-2">В наличии</th>
                      <th className="px-3 py-2">Фото</th>
                      <th className="px-3 py-2 w-24" />
                    </tr>
                  </thead>
                  <tbody>
                    {products.map((p) => (
                      <tr key={p.id} className="border-t border-slate-800">
                        <td className="px-3 py-2 text-slate-200">{p.name}</td>
                        <td className="px-3 py-2 text-slate-400">{p.price}</td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            min="0"
                            className="w-24 rounded border border-slate-600 bg-slate-950 px-2 py-1 text-xs text-white"
                            defaultValue={p.stock_quantity ?? 0}
                            key={`${p.id}-${p.stock_quantity}`}
                            onBlur={(e) => patchProductStock(p.id, e.target.value)}
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="file"
                            accept="image/*"
                            className="max-w-[180px] text-xs text-slate-400"
                            onChange={(e) => uploadProductPhoto(p.id, e.target.files?.[0])}
                          />
                        </td>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            className={`text-xs text-red-400 ${pressableSub}`}
                            onClick={() => deleteProduct(p.id)}
                          >
                            Удалить
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
