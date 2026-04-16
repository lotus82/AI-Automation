import { useMemo, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { IconDeleteButton } from "../components/ui/IconActionButtons.jsx";
import { useStorefrontCart } from "../store/storefrontCartStore.js";

function formatApiDetail(err) {
  const det = err?.response?.data?.detail ?? err?.detail;
  if (typeof det === "string") return det;
  if (Array.isArray(det)) return det.map((x) => x?.msg ?? x).join("; ");
  if (det != null) return JSON.stringify(det);
  return err?.message ?? String(err);
}

export function StoreCartPage() {
  const { slug: slugParam } = useParams();
  const { slug, catalog, loading, reloadCatalog } = useOutletContext();
  const s = slug || slugParam;

  const lines = useStorefrontCart((st) => st.bySlug[String(s || "")] || {});
  const setQty = useStorefrontCart((st) => st.setQty);
  const removeLine = useStorefrontCart((st) => st.removeLine);
  const clearSlug = useStorefrontCart((st) => st.clearSlug);

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [messenger, setMessenger] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [done, setDone] = useState(false);

  const byId = useMemo(() => {
    const map = new Map();
    for (const p of catalog?.products ?? []) {
      map.set(String(p.id), p);
    }
    return map;
  }, [catalog?.products]);

  const rows = useMemo(() => {
    const out = [];
    for (const [pid, qty] of Object.entries(lines)) {
      const q = parseInt(String(qty), 10) || 0;
      if (q <= 0) continue;
      const p = byId.get(String(pid));
      out.push({ pid, qty: q, p });
    }
    return out;
  }, [lines, byId]);

  const total = useMemo(() => {
    let t = 0;
    for (const { p, qty } of rows) {
      if (!p) continue;
      const price = parseFloat(String(p.price).replace(",", ".")) || 0;
      t += price * qty;
    }
    return t.toFixed(2);
  }, [rows]);

  const submitOrder = async (e) => {
    e.preventDefault();
    setMsg("");
    if (!s || rows.length === 0) return;
    const nm = name.trim();
    const ph = phone.trim();
    if (!nm || !ph) {
      setMsg("Укажите имя и телефон.");
      return;
    }
    const items = rows
      .filter((r) => r.p)
      .map((r) => ({
        product_id: r.p.id,
        quantity: r.qty,
      }));
    if (items.length === 0) {
      setMsg("В корзине нет доступных товаров. Обновите каталог.");
      return;
    }
    setBusy(true);
    try {
      const body = {
        name: nm,
        phone: ph,
        address: address.trim(),
        items,
      };
      if (messenger && messenger !== "none") {
        body.messenger = messenger;
      }
      const res = await fetch(`/api/public-store/${encodeURIComponent(s)}/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(typeof j?.detail === "string" ? j.detail : `HTTP ${res.status}`);
      }
      clearSlug(s);
      setDone(true);
      setName("");
      setPhone("");
      setAddress("");
      await reloadCatalog?.();
    } catch (err) {
      setMsg(formatApiDetail(err));
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <div className="rounded-2xl bg-[var(--store-card)] p-6 text-center ring-1 ring-[var(--store-border)]">
        <p className="text-lg font-semibold text-[var(--store-accent)]">Заказ принят</p>
        <p className="mt-2 text-sm text-[var(--store-muted)]">С вами свяжутся для подтверждения.</p>
        <button
          type="button"
          className="mt-6 w-full rounded-2xl bg-[var(--store-accent)] py-3 text-sm font-bold text-[var(--store-bg)]"
          onClick={() => setDone(false)}
        >
          Вернуться в корзину
        </button>
      </div>
    );
  }

  if (loading && !catalog) {
    return <div className="h-40 animate-pulse rounded-2xl bg-[var(--store-card)]" />;
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-2xl bg-[var(--store-card)] px-4 py-12 text-center ring-1 ring-[var(--store-border)]">
        <p className="text-[var(--store-muted)]">Корзина пуста</p>
        <p className="mt-1 text-xs text-[var(--store-muted)]">Добавьте товары в каталоге</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ul className="space-y-3">
        {rows.map(({ pid, qty, p }) => (
          <li
            key={pid}
            className="flex gap-3 rounded-2xl bg-[var(--store-card)] p-3 ring-1 ring-[var(--store-border)]"
          >
            <div className="h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-[color-mix(in_srgb,var(--store-bg)_70%,transparent)]">
              {p?.photo_url ? (
                <img src={p.photo_url} alt="" className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full items-center justify-center text-[var(--store-muted)]">◇</div>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="font-medium leading-snug">{p?.name ?? "Товар недоступен"}</div>
              {p ? (
                <div className="text-sm text-[var(--store-accent)]">{p.price} ₽</div>
              ) : (
                <div className="text-xs text-amber-400">Удалите позицию</div>
              )}
              {p ? (
                <div className="mt-2 flex items-center gap-2">
                  <button
                    type="button"
                    className="h-9 w-9 rounded-lg bg-[color-mix(in_srgb,var(--store-bg)_60%,transparent)] text-lg leading-none"
                    onClick={() => setQty(s, pid, qty - 1, p.stock_quantity)}
                    aria-label="Меньше"
                  >
                    −
                  </button>
                  <span className="min-w-[2rem] text-center text-sm font-semibold">{qty}</span>
                  <button
                    type="button"
                    className="h-9 w-9 rounded-lg bg-[color-mix(in_srgb,var(--store-bg)_60%,transparent)] text-lg leading-none"
                    onClick={() => setQty(s, pid, qty + 1, p.stock_quantity)}
                    aria-label="Больше"
                  >
                    +
                  </button>
                  <IconDeleteButton
                    title="Удалить из корзины"
                    className="ml-auto"
                    onClick={() => removeLine(s, pid)}
                  />
                </div>
              ) : (
                <IconDeleteButton
                  title="Удалить из корзины"
                  className="mt-2"
                  onClick={() => removeLine(s, pid)}
                />
              )}
            </div>
          </li>
        ))}
      </ul>

      <div className="flex items-center justify-between rounded-2xl bg-[color-mix(in_srgb,var(--store-card)_90%,transparent)] px-4 py-3 ring-1 ring-[var(--store-border)]">
        <span className="text-[var(--store-muted)]">Итого</span>
        <span className="text-xl font-bold text-[var(--store-accent)]">{total} ₽</span>
      </div>

      {msg ? (
        <p className="rounded-xl border border-red-500/30 bg-red-950/20 px-3 py-2 text-sm text-red-200">{msg}</p>
      ) : null}

      <form onSubmit={submitOrder} className="space-y-4 rounded-2xl bg-[var(--store-card)] p-4 ring-1 ring-[var(--store-border)]">
        <h2 className="text-sm font-semibold text-[var(--store-text)]">Оформление</h2>
        <label className="block text-xs text-[var(--store-muted)]">
          Имя
          <input
            required
            className="mt-1 w-full rounded-xl border border-[var(--store-border)] bg-[color-mix(in_srgb,var(--store-bg)_55%,transparent)] px-3 py-2.5 text-sm text-[var(--store-text)] outline-none focus:ring-2 focus:ring-[var(--store-accent)]/50"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
          />
        </label>
        <label className="block text-xs text-[var(--store-muted)]">
          Телефон
          <input
            required
            type="tel"
            className="mt-1 w-full rounded-xl border border-[var(--store-border)] bg-[color-mix(in_srgb,var(--store-bg)_55%,transparent)] px-3 py-2.5 text-sm text-[var(--store-text)] outline-none focus:ring-2 focus:ring-[var(--store-accent)]/50"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            autoComplete="tel"
          />
        </label>
        <label className="block text-xs text-[var(--store-muted)]">
          Адрес доставки
          <textarea
            rows={3}
            className="mt-1 w-full rounded-xl border border-[var(--store-border)] bg-[color-mix(in_srgb,var(--store-bg)_55%,transparent)] px-3 py-2.5 text-sm text-[var(--store-text)] outline-none focus:ring-2 focus:ring-[var(--store-accent)]/50"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="Город, улица, дом, квартира"
          />
        </label>
        <label className="block text-xs text-[var(--store-muted)]">
          Уведомить продавца (необязательно)
          <select
            className="mt-1 w-full rounded-xl border border-[var(--store-border)] bg-[color-mix(in_srgb,var(--store-bg)_55%,transparent)] px-3 py-2.5 text-sm text-[var(--store-text)]"
            value={messenger}
            onChange={(e) => setMessenger(e.target.value)}
          >
            <option value="">Не отправлять</option>
            <option value="max">MAX</option>
            <option value="telegram">Telegram</option>
            <option value="vk">VK</option>
          </select>
        </label>
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-2xl bg-[var(--store-accent)] py-3.5 text-sm font-bold text-[var(--store-bg)] shadow-lg disabled:opacity-50 active:scale-[0.99]"
        >
          {busy ? "Отправка…" : "Оформить заказ"}
        </button>
      </form>
    </div>
  );
}
