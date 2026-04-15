import { useCallback, useEffect, useMemo, useState } from "react";
import { Home, ShoppingBag } from "lucide-react";
import { NavLink, Outlet, useParams } from "react-router-dom";
import { useStorefrontCart } from "../../store/storefrontCartStore.js";

function themeToCssVars(theme) {
  if (!theme) return {};
  return {
    "--store-accent": theme.accent || "#6366f1",
    "--store-bg": theme.bg || "#0f172a",
    "--store-card": theme.card || "#1e293b",
    "--store-text": theme.text || "#f8fafc",
    "--store-muted": theme.muted || "#94a3b8",
    "--store-border": "color-mix(in srgb, var(--store-muted) 35%, transparent)",
  };
}

const navCls = ({ isActive }) =>
  [
    "flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium transition-colors",
    isActive ? "text-[var(--store-accent)]" : "text-[var(--store-muted)]",
  ].join(" ");

/**
 * Каркас публичной витрины: без сайдбара портала. Шапка, корзина, нижняя навигация (mobile-first).
 */
export function StoreLayout() {
  const { slug } = useParams();
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const lines = useStorefrontCart((s) => s.bySlug[String(slug || "")] || {});
  const cartCount = useMemo(
    () => Object.values(lines).reduce((a, q) => a + (parseInt(String(q), 10) || 0), 0),
    [lines],
  );

  const reload = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/public-store/${encodeURIComponent(slug)}?messenger=max`);
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(typeof j?.detail === "string" ? j.detail : `HTTP ${res.status}`);
      }
      setCatalog(await res.json());
    } catch (e) {
      setError(e?.message ?? String(e));
      setCatalog(null);
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    reload();
  }, [reload]);

  const cssVars = useMemo(() => themeToCssVars(catalog?.theme), [catalog?.theme]);
  const base = `/store/${encodeURIComponent(slug || "")}`;

  const outletCtx = useMemo(
    () => ({
      slug,
      catalog,
      loading,
      error,
      reloadCatalog: reload,
    }),
    [slug, catalog, loading, error, reload],
  );

  return (
    <div
      className="min-h-dvh flex flex-col bg-[var(--store-bg)] text-[var(--store-text)] antialiased"
      style={cssVars}
    >
      <header className="sticky top-0 z-20 border-b border-[var(--store-border)] bg-[color-mix(in_srgb,var(--store-card)_88%,transparent)] backdrop-blur-md">
        <div
          className="mx-auto flex max-w-lg items-center gap-3 px-3 py-3"
          style={{ paddingTop: "max(0.75rem, env(safe-area-inset-top, 0px))" }}
        >
          {catalog?.shop?.logo_url ? (
            <img
              src={catalog.shop.logo_url}
              alt=""
              className="h-10 w-10 shrink-0 rounded-2xl object-cover ring-1 ring-[var(--store-border)]"
            />
          ) : (
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--store-card)] text-lg font-bold text-[var(--store-accent)]">
              {(catalog?.shop?.name || slug || "?").slice(0, 1).toUpperCase()}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-base font-semibold leading-tight">
              {loading ? "…" : catalog?.shop?.name || "Витрина"}
            </h1>
            {catalog?.shop?.description ? (
              <p className="line-clamp-1 text-xs text-[var(--store-muted)]">{catalog.shop.description}</p>
            ) : null}
          </div>
          <NavLink
            to={`${base}/cart`}
            className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[var(--store-card)] text-[var(--store-text)] ring-1 ring-[var(--store-border)] active:scale-[0.97]"
            aria-label="Корзина"
          >
            <ShoppingBag className="h-5 w-5" strokeWidth={1.75} aria-hidden />
            {cartCount > 0 ? (
              <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--store-accent)] px-1 text-[10px] font-bold text-[var(--store-bg)]">
                {cartCount > 99 ? "99+" : cartCount}
              </span>
            ) : null}
          </NavLink>
        </div>
      </header>

      <main className="mx-auto w-full max-w-lg flex-1 px-3 py-4 pb-24">
        <Outlet context={outletCtx} />
      </main>

      <nav className="fixed bottom-0 left-0 right-0 z-20 border-t border-[var(--store-border)] bg-[color-mix(in_srgb,var(--store-card)_95%,transparent)] backdrop-blur-lg pb-[env(safe-area-inset-bottom,12px)] pt-1">
        <div className="mx-auto flex max-w-lg">
          <NavLink to={base} end className={navCls}>
            <Home className="h-6 w-6" strokeWidth={1.75} aria-hidden />
            Каталог
          </NavLink>
          <NavLink to={`${base}/cart`} className={navCls}>
            <ShoppingBag className="h-6 w-6" strokeWidth={1.75} aria-hidden />
            Корзина
            {cartCount > 0 ? (
              <span className="rounded-full bg-[var(--store-accent)]/20 px-1.5 text-[10px] text-[var(--store-accent)]">
                {cartCount}
              </span>
            ) : null}
          </NavLink>
        </div>
      </nav>
    </div>
  );
}
