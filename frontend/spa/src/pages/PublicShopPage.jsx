import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { ShoppingCart } from "lucide-react";
import { IconDeleteButton } from "../components/ui/IconActionButtons.jsx";
import { PAGE_H1, PAGE_TEXT } from "../styles/pageLayout.js";

const MESSENGERS = [
  { id: "max", label: "MAX" },
  { id: "telegram", label: "Telegram" },
  { id: "vk", label: "VK" },
];

function cartStorageKey(slug) {
  return `public_shop_cart:${slug || ""}`;
}

function readCart(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return {};
    const p = JSON.parse(raw);
    return p && typeof p === "object" ? p : {};
  } catch {
    return {};
  }
}

function writeCart(key, obj) {
  try {
    localStorage.setItem(key, JSON.stringify(obj));
  } catch {
    /* ignore */
  }
}

/** Привести корзину к актуальному каталогу и остаткам */
function reconcileCart(cartObj, products) {
  const byId = Object.fromEntries((products || []).map((p) => [String(p.id), p]));
  const next = {};
  for (const [id, q] of Object.entries(cartObj || {})) {
    const pr = byId[id];
    if (!pr) continue;
    const max = Math.max(0, Number(pr.stock_quantity) || 0);
    if (max <= 0) continue;
    const qq = Math.min(Math.max(1, parseInt(String(q), 10) || 1), max);
    next[id] = qq;
  }
  return next;
}

export function PublicShopPage() {
  const { slug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const messenger = (searchParams.get("messenger") || "max").toLowerCase();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);

  const [cartOpen, setCartOpen] = useState(false);
  const [cart, setCart] = useState({});
  const [buyerContact, setBuyerContact] = useState("");
  const [orderBusy, setOrderBusy] = useState(false);
  const [orderMsg, setOrderMsg] = useState("");
  const [orderErr, setOrderErr] = useState("");

  const load = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    setError("");
    try {
      const m = MESSENGERS.some((x) => x.id === messenger) ? messenger : "max";
      const res = await fetch(`/api/shops/public/${encodeURIComponent(slug)}?messenger=${encodeURIComponent(m)}`);
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j?.detail || `HTTP ${res.status}`);
      }
      setData(await res.json());
    } catch (e) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }, [slug, messenger]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setOrderMsg("");
  }, [messenger]);

  const ckey = useMemo(() => cartStorageKey(slug), [slug]);

  const products = data?.products ?? [];
  const activeMessenger = data?.messenger || messenger;

  useEffect(() => {
    if (!slug || !data) return;
    const stored = readCart(ckey);
    setCart(reconcileCart(stored, products));
  }, [slug, ckey, data, products]);

  useEffect(() => {
    if (!slug) return;
    writeCart(ckey, cart);
  }, [slug, ckey, cart]);

  const cssVars = useMemo(() => {
    if (!data?.theme) return {};
    const t = data.theme;
    return {
      "--shop-accent": t.accent || "#a78bfa",
      "--shop-bg": t.bg || "#0f172a",
      "--shop-card": t.card || "#1e293b",
      "--shop-text": t.text || "#f8fafc",
      "--shop-muted": t.muted || "#94a3b8",
    };
  }, [data]);

  const setMessenger = (id) => {
    const next = new URLSearchParams(searchParams);
    next.set("messenger", id);
    setSearchParams(next, { replace: true });
  };

  const productsById = useMemo(() => Object.fromEntries(products.map((p) => [String(p.id), p])), [products]);

  const cartLines = useMemo(() => {
    return Object.entries(cart)
      .map(([id, qty]) => {
        const p = productsById[id];
        if (!p) return null;
        const q = Math.max(1, parseInt(String(qty), 10) || 1);
        const price = parseFloat(String(p.price).replace(",", ".")) || 0;
        return { id, product: p, qty: q, lineSum: price * q };
      })
      .filter(Boolean);
  }, [cart, productsById]);

  const cartCount = useMemo(() => cartLines.reduce((s, l) => s + l.qty, 0), [cartLines]);
  const cartTotal = useMemo(() => cartLines.reduce((s, l) => s + l.lineSum, 0), [cartLines]);

  const addToCart = (productId) => {
    const id = String(productId);
    const p = productsById[id];
    if (!p) return;
    const max = Math.max(0, Number(p.stock_quantity) || 0);
    if (max <= 0) return;
    setCart((prev) => {
      const cur = Math.max(0, parseInt(String(prev[id] || 0), 10) || 0);
      const nextQty = cur <= 0 ? 1 : Math.min(cur + 1, max);
      return { ...prev, [id]: nextQty };
    });
    setOrderMsg("");
    setOrderErr("");
  };

  const setLineQty = (productId, raw) => {
    const id = String(productId);
    const p = productsById[id];
    if (!p) return;
    const max = Math.max(0, Number(p.stock_quantity) || 0);
    let q = parseInt(String(raw), 10) || 0;
    if (q <= 0) {
      setCart((prev) => {
        const { [id]: _, ...rest } = prev;
        return rest;
      });
      return;
    }
    q = Math.min(q, max);
    setCart((prev) => ({ ...prev, [id]: q }));
  };

  const removeLine = (productId) => {
    const id = String(productId);
    setCart((prev) => {
      const { [id]: _, ...rest } = prev;
      return rest;
    });
  };

  const submitOrder = async () => {
    if (!slug || !activeMessenger) return;
    const items = cartLines.map((l) => ({ product_id: l.id, quantity: l.qty }));
    if (!items.length) {
      setOrderErr("Корзина пуста.");
      return;
    }
    const contact = buyerContact.trim();
    if (!contact) {
      setOrderErr("Укажите контакт для связи (телефон, @username и т.д.).");
      return;
    }
    setOrderBusy(true);
    setOrderErr("");
    setOrderMsg("");
    try {
      const res = await fetch(`/api/shops/public/${encodeURIComponent(slug)}/order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messenger: activeMessenger,
          buyer_contact: contact,
          items,
        }),
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof j?.detail === "string" ? j.detail : JSON.stringify(j?.detail) || `HTTP ${res.status}`);
      }
      setOrderMsg(j?.message || "Ваш заказ принят, с вами свяжется продавец.");
      setCart({});
      writeCart(ckey, {});
      setBuyerContact("");
      setCartOpen(false);
    } catch (e) {
      setOrderErr(e?.message ?? String(e));
    } finally {
      setOrderBusy(false);
    }
  };

  if (!slug) {
    return <div className="p-6 text-center text-sm text-red-400">Некорректная ссылка.</div>;
  }

  if (loading) {
    return (
      <div
        className="min-h-[100dvh] flex items-center justify-center px-4 text-[var(--shop-muted,#94a3b8)]"
        style={{ ...cssVars, backgroundColor: "var(--shop-bg)" }}
      >
        Загрузка…
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-[100dvh] bg-slate-950 px-4 py-10 text-center text-sm text-red-400 safe-area-pb">
        {error}
      </div>
    );
  }

  const shop = data.shop;

  return (
    <div
      className="min-h-[100dvh] text-[length:15px] leading-relaxed antialiased pb-[max(5rem,env(safe-area-inset-bottom))] pt-[max(0.5rem,env(safe-area-inset-top))]"
      style={{
        ...cssVars,
        backgroundColor: "var(--shop-bg)",
        color: "var(--shop-text)",
      }}
    >
      <div className="mx-auto max-w-lg px-3 sm:px-4">
        <div className="sticky top-0 z-10 mb-3 flex flex-wrap items-center justify-center gap-1.5 py-2 backdrop-blur-sm sm:py-3 [-webkit-backdrop-filter:blur(8px)] bg-[color-mix(in_srgb,var(--shop-bg)_88%,transparent)]">
          {MESSENGERS.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => setMessenger(m.id)}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition active:scale-[0.97] ${
                (data.messenger || messenger) === m.id
                  ? "border-[var(--shop-accent)] bg-[color-mix(in_srgb,var(--shop-accent)_22%,transparent)] text-[var(--shop-text)]"
                  : "border-[color-mix(in_srgb,var(--shop-muted)_40%,transparent)] text-[var(--shop-muted)]"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {orderMsg ? (
          <div
            className="mb-3 rounded-xl border px-3 py-2.5 text-sm"
            style={{
              borderColor: "color-mix(in srgb, var(--shop-accent) 45%, transparent)",
              backgroundColor: "color-mix(in srgb, var(--shop-accent) 12%, var(--shop-card))",
              color: "var(--shop-text)",
            }}
            role="status"
          >
            {orderMsg}
          </div>
        ) : null}

        <header className="mb-5 rounded-2xl border border-[color-mix(in_srgb,var(--shop-muted)_35%,transparent)] bg-[var(--shop-card)] p-4 shadow-sm">
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-start">
            {shop.logo_url ? (
              <img
                src={shop.logo_url}
                alt=""
                className="h-16 w-16 shrink-0 rounded-xl border border-[color-mix(in_srgb,var(--shop-muted)_30%,transparent)] object-cover"
              />
            ) : (
              <div
                className="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl text-lg font-bold text-[var(--shop-accent)]"
                style={{ backgroundColor: "color-mix(in srgb, var(--shop-accent) 18%, var(--shop-card))" }}
              >
                {String(shop.name || "?")
                  .slice(0, 1)
                  .toUpperCase()}
              </div>
            )}
            <div className="min-w-0 flex-1 text-center sm:text-left">
              <h1 className="text-xl font-bold leading-tight text-[var(--shop-text)]">{shop.name}</h1>
              {shop.description ? (
                <p className="mt-1.5 text-sm text-[var(--shop-muted)]">{shop.description}</p>
              ) : null}
            </div>
          </div>
        </header>

        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-[var(--shop-muted)]">Каталог</p>
        <ul className="space-y-3">
          {products.length === 0 ? (
            <li className="rounded-xl border border-dashed border-[color-mix(in_srgb,var(--shop-muted)_40%,transparent)] px-4 py-8 text-center text-sm text-[var(--shop-muted)]">
              Пока нет товаров
            </li>
          ) : (
            products.map((p) => {
              const stock = Math.max(0, Number(p.stock_quantity) || 0);
              const canBuy = stock > 0;
              return (
                <li
                  key={p.id}
                  className="overflow-hidden rounded-2xl border border-[color-mix(in_srgb,var(--shop-muted)_28%,transparent)] bg-[var(--shop-card)] shadow-sm"
                >
                  {p.photo_url ? (
                    <div className="aspect-[16/10] w-full bg-[color-mix(in_srgb,var(--shop-muted)_12%,var(--shop-card))]">
                      <img src={p.photo_url} alt="" className="h-full w-full object-cover" loading="lazy" />
                    </div>
                  ) : null}
                  <div className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <h2 className="text-base font-semibold text-[var(--shop-text)]">{p.name}</h2>
                      <span className="shrink-0 rounded-lg bg-[color-mix(in_srgb,var(--shop-accent)_20%,transparent)] px-2 py-1 text-sm font-semibold text-[var(--shop-accent)]">
                        {p.price} руб.
                      </span>
                    </div>
                    <p className="mt-1.5 text-xs text-[var(--shop-muted)]">
                      {canBuy ? <>В наличии: {stock}</> : <span className="text-amber-600/90">Нет в наличии</span>}
                    </p>
                    {p.description ? (
                      <p className="mt-2 text-sm text-[var(--shop-muted)]">{p.description}</p>
                    ) : null}
                    <button
                      type="button"
                      disabled={!canBuy}
                      onClick={() => addToCart(p.id)}
                      className="mt-3 w-full rounded-xl border border-[color-mix(in_srgb,var(--shop-accent)_45%,transparent)] bg-[color-mix(in_srgb,var(--shop-accent)_18%,transparent)] py-2.5 text-sm font-semibold text-[var(--shop-accent)] transition enabled:active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45"
                    >
                      В корзину
                    </button>
                  </div>
                </li>
              );
            })
          )}
        </ul>
      </div>

      {cartCount > 0 ? (
        <button
          type="button"
          onClick={() => {
            setCartOpen(true);
            setOrderErr("");
            setOrderMsg("");
          }}
          className="fixed bottom-[max(1rem,env(safe-area-inset-bottom))] left-1/2 z-20 flex -translate-x-1/2 items-center gap-2 rounded-full border border-[color-mix(in_srgb,var(--shop-accent)_50%,transparent)] bg-[var(--shop-card)] px-5 py-3 text-sm font-semibold text-[var(--shop-text)] shadow-lg active:scale-[0.98]"
          style={{ boxShadow: "0 8px 32px color-mix(in srgb, var(--shop-text) 12%, transparent)" }}
        >
          <ShoppingCart className="h-5 w-5 text-[var(--shop-accent)]" strokeWidth={2} aria-hidden />
          Корзина{" "}
          <span className="rounded-full bg-[var(--shop-accent)] px-2 py-0.5 text-xs text-[var(--shop-bg)]">{cartCount}</span>
        </button>
      ) : null}

      {cartOpen ? (
        <div
          className="fixed inset-0 z-30 flex flex-col justify-end bg-black/50 p-0 sm:p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Корзина"
          onClick={() => setCartOpen(false)}
        >
          <div
            className="max-h-[85dvh] overflow-y-auto rounded-t-2xl border border-[color-mix(in_srgb,var(--shop-muted)_30%,transparent)] bg-[var(--shop-card)] p-4 shadow-2xl sm:mx-auto sm:max-w-lg sm:rounded-2xl"
            style={{ color: "var(--shop-text)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between gap-2">
              <h2 className="text-lg font-bold">Корзина</h2>
              <button
                type="button"
                className="rounded-lg px-2 py-1 text-sm text-[var(--shop-muted)] active:bg-[color-mix(in_srgb,var(--shop-muted)_15%,transparent)]"
                onClick={() => setCartOpen(false)}
              >
                Закрыть
              </button>
            </div>

            {orderMsg ? (
              <p className="mb-3 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">
                {orderMsg}
              </p>
            ) : null}
            {orderErr ? (
              <p className="mb-3 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">{orderErr}</p>
            ) : null}

            <ul className="space-y-3">
              {cartLines.length === 0 ? (
                <li className="text-sm text-[var(--shop-muted)]">Корзина пуста.</li>
              ) : (
                cartLines.map((l) => (
                  <li
                    key={l.id}
                    className="flex flex-wrap items-center gap-2 rounded-xl border border-[color-mix(in_srgb,var(--shop-muted)_25%,transparent)] bg-[color-mix(in_srgb,var(--shop-bg)_40%,var(--shop-card))] p-3"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="font-medium">{l.product.name}</div>
                      <div className="text-xs text-[var(--shop-muted)]">
                        {l.product.price} руб. × {l.qty} = {l.lineSum.toFixed(2)} руб.
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        className="h-9 w-9 rounded-lg border border-[color-mix(in_srgb,var(--shop-muted)_35%,transparent)] text-lg leading-none"
                        onClick={() => setLineQty(l.id, l.qty - 1)}
                        aria-label="Меньше"
                      >
                        −
                      </button>
                      <input
                        type="number"
                        min="1"
                        max={Math.max(1, Number(l.product.stock_quantity) || 1)}
                        className="h-9 w-14 rounded-lg border border-[color-mix(in_srgb,var(--shop-muted)_35%,transparent)] bg-transparent text-center text-sm"
                        value={l.qty}
                        onChange={(e) => setLineQty(l.id, e.target.value)}
                      />
                      <button
                        type="button"
                        className="h-9 w-9 rounded-lg border border-[color-mix(in_srgb,var(--shop-muted)_35%,transparent)] text-lg leading-none"
                        onClick={() => setLineQty(l.id, l.qty + 1)}
                        aria-label="Больше"
                      >
                        +
                      </button>
                      <IconDeleteButton
                        title="Удалить из корзины"
                        className="ml-1 border-[color-mix(in_srgb,var(--shop-muted)_35%,transparent)] text-red-400 hover:bg-red-950/25"
                        onClick={() => removeLine(l.id)}
                      />
                    </div>
                  </li>
                ))
              )}
            </ul>

            {cartLines.length > 0 ? (
              <>
                <p className="mt-4 text-right text-sm font-semibold">Итого: {cartTotal.toFixed(2)} руб.</p>
                <label className="mt-3 block text-sm">
                  <span className="text-[var(--shop-muted)]">Контакт для связи</span>
                  <input
                    type="text"
                    autoComplete="tel"
                    className="mt-1 w-full rounded-xl border border-[color-mix(in_srgb,var(--shop-muted)_35%,transparent)] bg-[color-mix(in_srgb,var(--shop-bg)_25%,var(--shop-card))] px-3 py-2.5 text-[var(--shop-text)]"
                    placeholder="Телефон, Telegram, MAX…"
                    value={buyerContact}
                    onChange={(e) => setBuyerContact(e.target.value)}
                  />
                </label>
                <button
                  type="button"
                  disabled={orderBusy}
                  onClick={submitOrder}
                  className="mt-4 w-full rounded-xl py-3 text-sm font-bold text-[var(--shop-bg)] disabled:opacity-50"
                  style={{ backgroundColor: "var(--shop-accent)" }}
                >
                  {orderBusy ? "Отправка…" : "Заказать"}
                </button>
              </>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
