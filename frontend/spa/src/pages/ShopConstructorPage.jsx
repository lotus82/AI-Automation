import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ChevronRight,
  Layers,
  Loader2,
  Package,
  Percent,
  Plus,
  Save,
  ScrollText,
  Settings2,
  ShoppingCart,
} from "lucide-react";
import { IconDeleteButton } from "../components/ui/IconActionButtons.jsx";
import api from "../api/client.js";
import { BTN_ADD, BTN_SAVE, ICON_BTN, PAGE_H1, PAGE_TEXT } from "../styles/pageLayout.js";

function formatApiDetail(err) {
  const det = err?.response?.data?.detail;
  if (typeof det === "string") return det;
  if (Array.isArray(det)) return det.map((x) => x?.msg ?? x).join("; ");
  if (det != null) return JSON.stringify(det);
  return err?.message ?? String(err);
}

const TABS = [
  { id: "categories", label: "Категории", icon: Layers },
  { id: "products", label: "Товары", icon: Package },
  { id: "pages", label: "Страницы", icon: ScrollText },
  { id: "orders", label: "Заказы", icon: ShoppingCart },
  { id: "discounts", label: "Скидки", icon: Percent },
];

function buildCategoryTree(flat) {
  const byParent = new Map();
  for (const c of flat) {
    const key = c.parent_id || "__root__";
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key).push(c);
  }
  for (const [, list] of byParent) {
    list.sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0) || a.name.localeCompare(b.name));
  }
  function walk(parentKey) {
    const rows = byParent.get(parentKey) || [];
    return rows.map((c) => ({
      ...c,
      children: walk(c.id),
    }));
  }
  return walk("__root__");
}

function CategoryTreeRow({ node, depth, onAddChild, onDelete }) {
  const pad = 12 + depth * 18;
  return (
    <>
      <div
        className="flex items-center justify-between gap-2 rounded-lg border border-slate-700/60 bg-slate-950/40 px-3 py-2"
        style={{ marginLeft: depth ? 0 : 0 }}
      >
        <div className="flex min-w-0 items-center gap-2" style={{ paddingLeft: pad }}>
          {depth ? <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-500" aria-hidden /> : null}
          <span className="truncate text-sm text-slate-200">{node.name}</span>
        </div>
        <div className="flex shrink-0 gap-1">
          <button
            type="button"
            onClick={() => onAddChild(node)}
            className="rounded border border-slate-600 px-2 py-0.5 text-[11px] text-sky-300 hover:bg-slate-800"
          >
            Подкатегория
          </button>
          <IconDeleteButton
            title="Удалить категорию"
            className="h-7 w-7"
            onClick={() => onDelete(node)}
          />
        </div>
      </div>
      {node.children?.length
        ? node.children.map((ch) => (
            <CategoryTreeRow
              key={ch.id}
              node={ch}
              depth={depth + 1}
              onAddChild={onAddChild}
              onDelete={onDelete}
            />
          ))
        : null}
    </>
  );
}

const pressable =
  "transition duration-100 ease-out select-none active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/60";

export function ShopConstructorPage() {
  const { shopId } = useParams();
  const [tab, setTab] = useState("categories");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const [detail, setDetail] = useState(null);
  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  const [pages, setPages] = useState([]);
  const [orders, setOrders] = useState([]);
  const [discounts, setDiscounts] = useState([]);

  const [shopName, setShopName] = useState("");
  const [shopDesc, setShopDesc] = useState("");
  const [shopSlug, setShopSlug] = useState("");

  const [catNewName, setCatNewName] = useState("");
  const [catParentId, setCatParentId] = useState(null);

  const [pageTitle, setPageTitle] = useState("");
  const [pageSlug, setPageSlug] = useState("");
  const [pageContent, setPageContent] = useState("");
  const [editPageId, setEditPageId] = useState(null);

  const [discName, setDiscName] = useState("");
  const [discPct, setDiscPct] = useState("");
  const [discStart, setDiscStart] = useState("");
  const [discEnd, setDiscEnd] = useState("");

  const [pName, setPName] = useState("");
  const [pDesc, setPDesc] = useState("");
  const [pPrice, setPPrice] = useState("");
  const [pStock, setPStock] = useState("0");
  const [pSort, setPSort] = useState("0");
  const [pCategory, setPCategory] = useState("");
  const [pTag, setPTag] = useState("");
  const [pFile, setPFile] = useState(null);

  const tree = useMemo(() => buildCategoryTree(categories), [categories]);

  const loadAll = useCallback(async () => {
    if (!shopId) return;
    setMsg("");
    try {
      const [d, c, pr, pg, or, di] = await Promise.all([
        api.get(`/shops/${shopId}`),
        api.get(`/shops/${shopId}/categories`),
        api.get(`/shops/${shopId}/products`),
        api.get(`/shops/${shopId}/static-pages`),
        api.get(`/shops/${shopId}/orders`),
        api.get(`/shops/${shopId}/discounts`),
      ]);
      setDetail(d.data);
      setShopName(d.data.name ?? "");
      setShopDesc(d.data.description ?? "");
      setShopSlug(d.data.slug ?? "");
      setCategories(c.data ?? []);
      setProducts(pr.data ?? []);
      setPages(pg.data ?? []);
      setOrders(or.data ?? []);
      setDiscounts(di.data ?? []);
    } catch (e) {
      setMsg(formatApiDetail(e));
    }
  }, [shopId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const saveShopBasics = async () => {
    if (!shopId) return;
    setBusy(true);
    setMsg("");
    try {
      await api.patch(`/shops/${shopId}`, {
        name: shopName.trim(),
        description: shopDesc.trim(),
        slug: shopSlug.trim() || undefined,
      });
      await loadAll();
      setMsg("Настройки магазина сохранены.");
    } catch (e) {
      setMsg(formatApiDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const onLogo = async (file) => {
    if (!shopId || !file) return;
    const fd = new FormData();
    fd.append("file", file);
    setBusy(true);
    setMsg("");
    try {
      await api.post(`/shops/${shopId}/logo`, fd);
      await loadAll();
    } catch (e) {
      setMsg(formatApiDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const addCategory = async (e) => {
    e.preventDefault();
    const name = catNewName.trim();
    if (!name || !shopId) return;
    setBusy(true);
    setMsg("");
    try {
      await api.post(`/shops/${shopId}/categories`, {
        name,
        description: "",
        parent_id: catParentId,
        order_index: 0,
      });
      setCatNewName("");
      await loadAll();
    } catch (e) {
      setMsg(formatApiDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const deleteCategory = async (node) => {
    if (!shopId || !window.confirm(`Удалить категорию «${node.name}»?`)) return;
    setBusy(true);
    try {
      await api.delete(`/shops/${shopId}/categories/${node.id}`);
      await loadAll();
    } catch (e) {
      setMsg(formatApiDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const savePage = async (e) => {
    e.preventDefault();
    if (!shopId) return;
    const title = pageTitle.trim();
    const slug = pageSlug.trim().toLowerCase();
    if (!title || !slug) {
      setMsg("Укажите заголовок и slug страницы.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      if (editPageId) {
        await api.patch(`/shops/${shopId}/static-pages/${editPageId}`, {
          title,
          slug,
          content: pageContent,
        });
      } else {
        await api.post(`/shops/${shopId}/static-pages`, {
          title,
          slug,
          content: pageContent,
        });
      }
      setPageTitle("");
      setPageSlug("");
      setPageContent("");
      setEditPageId(null);
      await loadAll();
    } catch (e) {
      setMsg(formatApiDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const startEditPage = (p) => {
    setEditPageId(p.id);
    setPageTitle(p.title);
    setPageSlug(p.slug);
    setPageContent(p.content ?? "");
    setTab("pages");
  };

  const addDiscount = async (e) => {
    e.preventDefault();
    if (!shopId) return;
    const name = discName.trim();
    const pct = discPct.replace(",", ".").trim();
    if (!name || !pct || !discStart || !discEnd) {
      setMsg("Заполните все поля скидки.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      await api.post(`/shops/${shopId}/discounts`, {
        name,
        percentage: pct,
        start_date: discStart,
        end_date: discEnd,
      });
      setDiscName("");
      setDiscPct("");
      setDiscStart("");
      setDiscEnd("");
      await loadAll();
    } catch (e) {
      setMsg(formatApiDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const deleteDiscount = async (id) => {
    if (!shopId || !window.confirm("Удалить скидку?")) return;
    try {
      await api.delete(`/shops/${shopId}/discounts/${id}`);
      await loadAll();
    } catch (e) {
      setMsg(formatApiDetail(e));
    }
  };

  const addProduct = async (e) => {
    e.preventDefault();
    if (!shopId) return;
    const price = pPrice.replace(",", ".").trim();
    if (!pName.trim() || !price) {
      setMsg("Товар: укажите название и цену.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      const body = {
        name: pName.trim(),
        description: pDesc.trim(),
        price,
        stock_quantity: Math.max(0, parseInt(pStock, 10) || 0),
        sort_order: parseInt(pSort, 10) || 0,
        category_id: pCategory || null,
        tag: pTag || null,
        is_active: true,
      };
      const { data: created } = await api.post(`/shops/${shopId}/products`, body);
      if (pFile) {
        const fd = new FormData();
        fd.append("file", pFile);
        await api.post(`/shops/${shopId}/products/${created.id}/photo`, fd);
      }
      setPName("");
      setPDesc("");
      setPPrice("");
      setPStock("0");
      setPSort("0");
      setPCategory("");
      setPTag("");
      setPFile(null);
      await loadAll();
    } catch (e) {
      setMsg(formatApiDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const deleteProduct = async (pid) => {
    if (!shopId || !window.confirm("Удалить товар?")) return;
    try {
      await api.delete(`/shops/${shopId}/products/${pid}`);
      await loadAll();
    } catch (e) {
      setMsg(formatApiDetail(e));
    }
  };

  const patchProductStock = async (pid, raw) => {
    const n = Math.max(0, parseInt(String(raw), 10) || 0);
    if (!shopId) return;
    setBusy(true);
    try {
      await api.patch(`/shops/${shopId}/products/${pid}`, { stock_quantity: n });
      await loadAll();
    } catch (e) {
      setMsg(formatApiDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const toggleProductActive = async (p) => {
    if (!shopId) return;
    try {
      await api.patch(`/shops/${shopId}/products/${p.id}`, { is_active: !p.is_active });
      await loadAll();
    } catch (e) {
      setMsg(formatApiDetail(e));
    }
  };

  const uploadProductPhoto = async (pid, file) => {
    if (!shopId || !file) return;
    const fd = new FormData();
    fd.append("file", file);
    setBusy(true);
    try {
      await api.post(`/shops/${shopId}/products/${pid}/photo`, fd);
      await loadAll();
    } catch (e) {
      setMsg(formatApiDetail(e));
    } finally {
      setBusy(false);
    }
  };

  if (!shopId) {
    return <p className="text-slate-400">Некорректный маршрут.</p>;
  }

  const publicUrl = detail?.slug
    ? `${window.location.origin}/public/shop/${detail.slug}`
    : "";

  return (
    <div className="w-full min-w-0 space-y-6 pb-12 text-slate-100">
      <div className="flex flex-wrap items-start gap-4">
        <Link
          to="/shops"
          className={`inline-flex items-center gap-2 rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-300 hover:bg-slate-800 ${pressable}`}
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          К списку
        </Link>
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold text-white md:text-2xl">
            Конструктор: {detail?.name ?? <span className="text-slate-500">загрузка…</span>}
          </h1>
          {publicUrl ? (
            <p className="mt-1 truncate text-xs text-slate-500">
              Витрина:{" "}
              <a href={publicUrl} className="text-emerald-300/90 hover:underline" target="_blank" rel="noreferrer">
                {publicUrl}
              </a>
            </p>
          ) : null}
        </div>
        {busy ? <Loader2 className="h-5 w-5 animate-spin text-emerald-400" aria-hidden /> : null}
      </div>

      {msg ? (
        <p className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-300">{msg}</p>
      ) : null}

      <section className="rounded-xl border border-slate-700/80 bg-slate-900/40 p-4">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
          <Settings2 className="h-4 w-4 text-slate-400" aria-hidden />
          Основные данные магазина
        </h2>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-xs text-slate-400">
            Название
            <input
              className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
              value={shopName}
              onChange={(e) => setShopName(e.target.value)}
            />
          </label>
          <label className="text-xs text-slate-400">
            Slug
            <input
              className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
              value={shopSlug}
              onChange={(e) => setShopSlug(e.target.value.toLowerCase())}
            />
          </label>
          <label className="md:col-span-2 text-xs text-slate-400">
            Описание
            <textarea
              className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
              rows={2}
              value={shopDesc}
              onChange={(e) => setShopDesc(e.target.value)}
            />
          </label>
          <label className="text-xs text-slate-400">
            Логотип
            <input
              type="file"
              accept="image/*"
              className="mt-1 block w-full text-xs text-slate-500"
              onChange={(e) => onLogo(e.target.files?.[0])}
            />
          </label>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={saveShopBasics}
          className={`${BTN_SAVE} mt-3 ${pressable}`}
        >
          <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
          Сохранить основные данные
        </button>
      </section>

      <div className="flex flex-wrap gap-1 border-b border-slate-700 pb-1">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`inline-flex items-center gap-2 rounded-t-lg px-3 py-2 text-sm font-medium ${
              tab === id
                ? "bg-slate-800 text-white"
                : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
            }`}
          >
            <Icon className="h-4 w-4" strokeWidth={1.75} aria-hidden />
            {label}
          </button>
        ))}
      </div>

      {tab === "categories" ? (
        <section className="space-y-4 rounded-xl border border-slate-700/60 bg-slate-900/30 p-4">
          <h3 className="text-sm font-semibold text-slate-200">Дерево категорий</h3>
          <p className="text-xs text-slate-500">
            Добавьте корневую категорию или подкатегорию для выбранного узла.
            {catParentId ? (
              <>
                {" "}
                Родитель:{" "}
                <button
                  type="button"
                  className="text-sky-400 underline"
                  onClick={() => setCatParentId(null)}
                >
                  сбросить
                </button>
              </>
            ) : null}
          </p>
          <form onSubmit={addCategory} className="flex flex-wrap items-end gap-2">
            <input
              className="min-w-[200px] flex-1 rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
              placeholder="Название категории"
              value={catNewName}
              onChange={(e) => setCatNewName(e.target.value)}
            />
            <button
              type="submit"
              disabled={busy}
              className={`${BTN_ADD} disabled:opacity-50`}
            >
              <Plus className={ICON_BTN} strokeWidth={2} aria-hidden />
              {catParentId ? "Добавить подкатегорию" : "Добавить категорию"}
            </button>
          </form>
          <div className="space-y-1">
            {tree.length === 0 ? (
              <p className="text-sm text-slate-500">Категорий пока нет.</p>
            ) : (
              tree.map((n) => (
                <CategoryTreeRow
                  key={n.id}
                  node={n}
                  depth={0}
                  onAddChild={(node) => setCatParentId(node.id)}
                  onDelete={deleteCategory}
                />
              ))
            )}
          </div>
        </section>
      ) : null}

      {tab === "products" ? (
        <section className="space-y-4 rounded-xl border border-slate-700/60 bg-slate-900/30 p-4">
          <h3 className="text-sm font-semibold text-slate-200">Новая карточка товара</h3>
          <form className="grid gap-3 md:grid-cols-2 lg:grid-cols-3" onSubmit={addProduct}>
            <input
              className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
              placeholder="Название"
              value={pName}
              onChange={(e) => setPName(e.target.value)}
              required
            />
            <input
              className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
              placeholder="Цена"
              value={pPrice}
              onChange={(e) => setPPrice(e.target.value)}
              required
            />
            <select
              className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
              value={pCategory}
              onChange={(e) => setPCategory(e.target.value)}
            >
              <option value="">Без категории</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <select
              className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
              value={pTag}
              onChange={(e) => setPTag(e.target.value)}
            >
              <option value="">Без тега</option>
              <option value="new">Новинка</option>
              <option value="sale">Скидка</option>
              <option value="hot">Хит</option>
            </select>
            <input
              type="number"
              min="0"
              className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
              placeholder="Остаток"
              value={pStock}
              onChange={(e) => setPStock(e.target.value)}
            />
            <input
              type="number"
              className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
              placeholder="Порядок"
              value={pSort}
              onChange={(e) => setPSort(e.target.value)}
            />
            <label className="md:col-span-2 lg:col-span-3 text-xs text-slate-400">
              Фото (основное)
              <input
                type="file"
                accept="image/*"
                className="mt-1 block w-full text-xs"
                onChange={(e) => setPFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <textarea
              className="md:col-span-2 lg:col-span-3 rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
              rows={2}
              placeholder="Описание"
              value={pDesc}
              onChange={(e) => setPDesc(e.target.value)}
            />
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              Создать товар
            </button>
          </form>

          <h4 className="pt-4 text-sm font-medium text-slate-300">Список товаров</h4>
          <div className="overflow-x-auto rounded border border-slate-700">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-slate-700 bg-slate-900/60 text-xs uppercase text-slate-400">
                <tr>
                  <th className="px-2 py-2">Название</th>
                  <th className="px-2 py-2">Цена</th>
                  <th className="px-2 py-2">Тег</th>
                  <th className="px-2 py-2">Активен</th>
                  <th className="px-2 py-2">Остаток</th>
                  <th className="px-2 py-2">Фото</th>
                  <th className="px-2 py-2 w-20" />
                </tr>
              </thead>
              <tbody>
                {products.map((p) => (
                  <tr key={p.id} className="border-t border-slate-800">
                    <td className="px-2 py-2 text-slate-200">{p.name}</td>
                    <td className="px-2 py-2 text-slate-400">{p.price}</td>
                    <td className="px-2 py-2 text-slate-500">{p.tag ?? "—"}</td>
                    <td className="px-2 py-2">
                      <button
                        type="button"
                        onClick={() => toggleProductActive(p)}
                        className={`rounded px-2 py-0.5 text-xs ${p.is_active ? "bg-emerald-900/40 text-emerald-300" : "bg-slate-800 text-slate-500"}`}
                      >
                        {p.is_active ? "да" : "нет"}
                      </button>
                    </td>
                    <td className="px-2 py-2">
                      <input
                        type="number"
                        min="0"
                        className="w-20 rounded border border-slate-600 bg-slate-950 px-1 py-0.5 text-xs"
                        defaultValue={p.stock_quantity ?? 0}
                        key={`${p.id}-${p.stock_quantity}`}
                        onBlur={(e) => patchProductStock(p.id, e.target.value)}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <input
                        type="file"
                        accept="image/*"
                        className="max-w-[140px] text-[10px] text-slate-500"
                        onChange={(e) => uploadProductPhoto(p.id, e.target.files?.[0])}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <IconDeleteButton title="Удалить товар" onClick={() => deleteProduct(p.id)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {tab === "pages" ? (
        <section className="grid gap-6 lg:grid-cols-[minmax(0,280px)_1fr] rounded-xl border border-slate-700/60 bg-slate-900/30 p-4">
          <div>
            <h3 className="text-sm font-semibold text-slate-200">Страницы</h3>
            <p className="mt-1 text-xs text-slate-500">«О магазине», «Контакты» и др.</p>
            <ul className="mt-3 space-y-1">
              {pages.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    onClick={() => startEditPage(p)}
                    className={`w-full rounded border px-2 py-1.5 text-left text-sm ${
                      editPageId === p.id
                        ? "border-emerald-600 bg-emerald-950/30 text-white"
                        : "border-slate-700 bg-slate-950/50 text-slate-300 hover:border-slate-600"
                    }`}
                  >
                    <span className="font-medium">{p.title}</span>
                    <span className="block text-[11px] text-slate-500">/{p.slug}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
          <form onSubmit={savePage} className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-200">
              {editPageId ? "Редактирование" : "Новая страница"}
            </h3>
            {editPageId ? (
              <button
                type="button"
                className="text-xs text-sky-400 hover:underline"
                onClick={() => {
                  setEditPageId(null);
                  setPageTitle("");
                  setPageSlug("");
                  setPageContent("");
                }}
              >
                Очистить и создать новую
              </button>
            ) : null}
            <label className="block text-xs text-slate-400">
              Заголовок
              <input
                className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
                value={pageTitle}
                onChange={(e) => setPageTitle(e.target.value)}
                required
              />
            </label>
            <label className="block text-xs text-slate-400">
              Slug (латиница)
              <input
                className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
                value={pageSlug}
                onChange={(e) => setPageSlug(e.target.value.toLowerCase())}
                required
              />
            </label>
            <div className="flex flex-wrap gap-1 text-[11px]">
              {["about", "contacts", "delivery"].map((s) => (
                <button
                  key={s}
                  type="button"
                  className="rounded border border-slate-600 px-2 py-0.5 text-slate-400 hover:bg-slate-800"
                  onClick={() => setPageSlug(s)}
                >
                  {s}
                </button>
              ))}
            </div>
            <label className="block text-xs text-slate-400">
              Контент
              <textarea
                className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-2 py-1.5 font-mono text-sm"
                rows={12}
                value={pageContent}
                onChange={(e) => setPageContent(e.target.value)}
              />
            </label>
            <button
              type="submit"
              disabled={busy}
              className={
                editPageId
                  ? `${BTN_SAVE} disabled:opacity-50`
                  : "rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              }
            >
              {editPageId ? (
                <>
                  <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
                  Сохранить
                </>
              ) : (
                "Создать страницу"
              )}
            </button>
          </form>
        </section>
      ) : null}

      {tab === "orders" ? (
        <section className="space-y-3 rounded-xl border border-slate-700/60 bg-slate-900/30 p-4">
          <h3 className="text-sm font-semibold text-slate-200">Заказы</h3>
          {orders.length === 0 ? (
            <p className="text-sm text-slate-500">Заказов в базе нет (оформление через публичную витрину).</p>
          ) : (
            <div className="space-y-3">
              {orders.map((o) => (
                <div key={o.id} className="rounded border border-slate-700 bg-slate-950/40 p-3 text-sm">
                  <div className="flex flex-wrap justify-between gap-2">
                    <span className="font-mono text-xs text-slate-500">{o.id}</span>
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-amber-200">{o.status}</span>
                  </div>
                  <div className="mt-2 grid gap-1 text-slate-400">
                    <div>
                      Клиент:{" "}
                      {[o.customer_info?.name, o.customer_info?.phone].filter(Boolean).join(" · ") ||
                        JSON.stringify(o.customer_info)}
                    </div>
                    <div>Сумма: {o.total_amount}</div>
                    <div>Адрес: {o.delivery_address || "—"}</div>
                    <div>Статус доставки: {o.delivery_status || "—"}</div>
                    {o.items?.length ? (
                      <ul className="mt-2 list-inside list-disc text-xs text-slate-500">
                        {o.items.map((it) => (
                          <li key={it.id}>
                            товар {it.product_id}: ×{it.quantity} @ {it.price_at_time}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {tab === "discounts" ? (
        <section className="space-y-4 rounded-xl border border-slate-700/60 bg-slate-900/30 p-4">
          <h3 className="text-sm font-semibold text-slate-200">Скидки</h3>
          <form onSubmit={addDiscount} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <input
              className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
              placeholder="Название"
              value={discName}
              onChange={(e) => setDiscName(e.target.value)}
            />
            <input
              className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm"
              placeholder="% "
              value={discPct}
              onChange={(e) => setDiscPct(e.target.value)}
            />
            <input
              type="date"
              className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
              value={discStart}
              onChange={(e) => setDiscStart(e.target.value)}
            />
            <input
              type="date"
              className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
              value={discEnd}
              onChange={(e) => setDiscEnd(e.target.value)}
            />
            <button type="submit" disabled={busy} className={`${BTN_ADD} disabled:opacity-50`}>
              <Plus className={ICON_BTN} strokeWidth={2} aria-hidden />
              Добавить
            </button>
          </form>
          <ul className="space-y-2">
            {discounts.map((d) => (
              <li
                key={d.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-700 bg-slate-950/40 px-3 py-2 text-sm"
              >
                <span>
                  {d.name} — {d.percentage}% ({d.start_date} — {d.end_date})
                </span>
                <IconDeleteButton title="Удалить скидку" onClick={() => deleteDiscount(d.id)} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
