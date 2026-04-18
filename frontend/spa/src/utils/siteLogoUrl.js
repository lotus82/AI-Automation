/**
 * Приводит URL загруженного логотипа к пути на текущем origin (как отдаёт API после нормализации).
 * @param {string | null | undefined} url
 * @returns {string}
 */
export function normalizeSiteLogoUrl(url) {
  if (url == null || typeof url !== "string") return "";
  const s = url.trim();
  if (!s) return "";
  if (s.startsWith("/")) return s;
  try {
    const base = typeof window !== "undefined" ? window.location.origin : "http://localhost";
    const u = new URL(s, base);
    if (u.pathname.startsWith("/api/public/sites/assets/")) {
      return u.pathname + (u.search || "");
    }
  } catch {
    /* ignore */
  }
  return s;
}

/**
 * Значение для атрибута src у <img>: для путей с ведущим «/» подставляет origin окна
 * (надёжнее во встроенных WebView, чем относительный путь).
 * @param {string | null | undefined} url
 * @returns {string}
 */
export function siteLogoImgSrc(url) {
  const s = normalizeSiteLogoUrl(url);
  if (!s) return "";
  if (typeof window !== "undefined" && s.startsWith("/")) {
    return `${window.location.origin}${s}`;
  }
  return s;
}
