/**
 * Открытие ссылки из Mini App: во внешнем браузере через MAX Bridge (как обычный переход по ссылке),
 * иначе fallback. Нужно для оплаты Сбера и др.: внутри WebView платёж часто падает с ошибкой.
 *
 * @see https://dev.max.ru/docs/webapps/bridge — window.WebApp.openLink
 * @param {string} href
 */
export function openExternalLinkFromMiniApp(href) {
  if (typeof window === "undefined") return;
  const t = String(href || "").trim();
  if (!t || t.startsWith("#")) return;
  if (/^javascript:/i.test(t)) return;

  const win = window;
  const wa = win.WebApp || win.Telegram?.WebApp || win.MaxWebApp || win.maxWebApp;
  const openLink = wa && typeof wa.openLink === "function" ? wa.openLink.bind(wa) : null;

  const low = t.toLowerCase();
  if (low.startsWith("mailto:") || low.startsWith("tel:") || low.startsWith("sms:")) {
    win.location.assign(t);
    return;
  }

  if (openLink) {
    try {
      openLink(t);
      return;
    } catch {
      /* fall through */
    }
  }

  if (low.startsWith("http://") || low.startsWith("https://")) {
    try {
      win.open(t, "_blank", "noopener,noreferrer");
      return;
    } catch {
      /* fall through */
    }
  }

  try {
    win.location.assign(t);
  } catch {
    try {
      win.open(t, "_blank", "noopener,noreferrer");
    } catch {
      /* ignore */
    }
  }
}
