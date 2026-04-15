import { create } from "zustand";
import { persist } from "zustand/middleware";

function sumLines(lines) {
  if (!lines || typeof lines !== "object") return 0;
  return Object.values(lines).reduce((acc, q) => acc + (parseInt(String(q), 10) || 0), 0);
}

export const useStorefrontCart = create(
  persist(
    (set, get) => ({
      /** @type {Record<string, Record<string, number>>} */
      bySlug: {},

      addToCart(slug, productId, maxStock) {
        const key = String(slug || "");
        const pid = String(productId);
        const max = Math.max(0, parseInt(String(maxStock), 10) || 0);
        if (!key || max <= 0) return;
        set((state) => {
          const lines = { ...(state.bySlug[key] || {}) };
          const cur = Math.max(0, parseInt(String(lines[pid] || 0), 10) || 0);
          const next = Math.min(max, cur + 1);
          lines[pid] = next;
          return { bySlug: { ...state.bySlug, [key]: lines } };
        });
      },

      setQty(slug, productId, qty, maxStock) {
        const key = String(slug || "");
        const pid = String(productId);
        const max = Math.max(0, parseInt(String(maxStock), 10) || 0);
        if (!key) return;
        set((state) => {
          const lines = { ...(state.bySlug[key] || {}) };
          let q = Math.max(0, parseInt(String(qty), 10) || 0);
          q = Math.min(max, q);
          if (q <= 0) delete lines[pid];
          else lines[pid] = q;
          return { bySlug: { ...state.bySlug, [key]: lines } };
        });
      },

      removeLine(slug, productId) {
        const key = String(slug || "");
        const pid = String(productId);
        if (!key) return;
        set((state) => {
          const lines = { ...(state.bySlug[key] || {}) };
          delete lines[pid];
          return { bySlug: { ...state.bySlug, [key]: lines } };
        });
      },

      clearSlug(slug) {
        const key = String(slug || "");
        if (!key) return;
        set((state) => {
          const next = { ...state.bySlug };
          delete next[key];
          return { bySlug: next };
        });
      },

      getLines(slug) {
        return { ...(get().bySlug[String(slug || "")] || {}) };
      },

      countItems(slug) {
        return sumLines(get().bySlug[String(slug || "")]);
      },
    }),
    { name: "storefront-cart-v1" },
  ),
);
