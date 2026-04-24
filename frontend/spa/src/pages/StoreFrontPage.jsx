import { useMemo, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { Plus } from "lucide-react";
import { useStorefrontCart } from "../store/storefrontCartStore.js";
import { PAGE_H1, PAGE_TEXT } from "../styles/pageLayout.js";

const cardCls =
  "flex flex-col overflow-hidden rounded-2xl bg-[var(--store-card)] shadow-lg shadow-black/20 ring-1 ring-[var(--store-border)]";

export function StoreFrontPage() {
  const { slug: slugParam } = useParams();
  const { slug, catalog, loading, error, reloadCatalog } = useOutletContext();
  const s = slug || slugParam;

  const [selectedCategoryId, setSelectedCategoryId] = useState(null);

  const addToCart = useStorefrontCart((x) => x.addToCart);

  const products = catalog?.products ?? [];
  const categories = catalog?.categories ?? [];

  const filtered = useMemo(() => {
    if (!selectedCategoryId) return products;
    return products.filter((p) => String(p.category_id || "") === String(selectedCategoryId));
  }, [products, selectedCategoryId]);

  if (loading && !catalog) {
    return (
      <div className="space-y-3 animate-pulse">
        <div className="h-10 rounded-2xl bg-[var(--store-card)]" />
        <div className="grid grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className={`${cardCls} h-52`} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-red-950/30 px-4 py-3 text-sm text-red-200">
        {error}
        <button
          type="button"
          className="mt-3 block w-full rounded-xl bg-[var(--store-accent)] py-2 text-center text-sm font-semibold text-[var(--store-bg)]"
          onClick={() => reloadCatalog?.()}
        >
          Повторить
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="-mx-1 flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <button
          type="button"
          onClick={() => setSelectedCategoryId(null)}
          className={`shrink-0 rounded-full px-4 py-2 text-sm font-medium transition-all ${
            selectedCategoryId == null
              ? "bg-[var(--store-accent)] text-[var(--store-bg)]"
              : "bg-[var(--store-card)] text-[var(--store-muted)] ring-1 ring-[var(--store-border)]"
          }`}
        >
          Все
        </button>
        {categories.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => setSelectedCategoryId(c.id)}
            className={`shrink-0 rounded-full px-4 py-2 text-sm font-medium transition-all ${
              String(selectedCategoryId) === String(c.id)
                ? "bg-[var(--store-accent)] text-[var(--store-bg)]"
                : "bg-[var(--store-card)] text-[var(--store-muted)] ring-1 ring-[var(--store-border)]"
            }`}
          >
            {c.name}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <p className="py-12 text-center text-sm text-[var(--store-muted)]">В этой категории пока нет товаров.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-2">
          {filtered.map((p) => (
            <article key={p.id} className={cardCls}>
              <div className="aspect-square w-full bg-[color-mix(in_srgb,var(--store-bg)_80%,transparent)]">
                {p.photo_url ? (
                  <img src={p.photo_url} alt="" className="h-full w-full object-cover" loading="lazy" />
                ) : (
                  <div className="flex h-full items-center justify-center text-3xl text-[var(--store-muted)]">◇</div>
                )}
              </div>
              <div className="flex flex-1 flex-col gap-2 p-3">
                <h2 className="line-clamp-2 min-h-[2.5rem] text-sm font-semibold leading-snug">{p.name}</h2>
                <div className="mt-auto flex items-end justify-between gap-2">
                  <div>
                    <div className="text-base font-bold text-[var(--store-accent)]">{p.price} ₽</div>
                    {p.stock_quantity <= 3 && p.stock_quantity > 0 ? (
                      <div className="text-[10px] text-amber-400">Осталось {p.stock_quantity}</div>
                    ) : null}
                    {p.stock_quantity <= 0 ? (
                      <div className="text-[10px] text-[var(--store-muted)]">Нет в наличии</div>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    disabled={p.stock_quantity <= 0}
                    onClick={() => addToCart(s, p.id, p.stock_quantity)}
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--store-accent)] text-[var(--store-bg)] shadow-md disabled:opacity-40 active:scale-95"
                    aria-label="В корзину"
                  >
                    <Plus className="h-5 w-5" strokeWidth={2.5} aria-hidden />
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
