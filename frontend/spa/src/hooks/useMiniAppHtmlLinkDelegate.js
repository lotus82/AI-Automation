import { useEffect, useRef } from "react";
import { openExternalLinkFromMiniApp } from "../utils/miniAppOpenExternalLink.js";

/**
 * Ссылки в HTML страницы: в WebView MAX навигация по https отличается от внешнего браузера
 * (платёж Сбера и др.). Открываем через WebApp.openLink / см. miniAppOpenExternalLink.
 * mailto/tel/sms — без перехвата.
 *
 * @param {string | undefined} html
 * @param {{ forceExternal?: boolean }} [options] — в превью админки: открывать https в новой вкладке
 * @returns {React.RefObject<HTMLDivElement | null>}
 */
export function useMiniAppHtmlLinkDelegate(html, options = {}) {
  const { forceExternal = false } = options;
  const ref = useRef(null);

  useEffect(() => {
    const root = ref.current;
    if (!root) return undefined;

    const onClickCapture = (e) => {
      if (!(e.target instanceof Element)) return;
      const anchor = e.target.closest("a[href]");
      if (!anchor || !root.contains(anchor)) return;
      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#")) return;
      const t = href.trim();
      if (/^javascript:/i.test(t)) return;
      const low = t.toLowerCase();
      if (low.startsWith("mailto:") || low.startsWith("tel:") || low.startsWith("sms:")) return;

      e.preventDefault();
      e.stopPropagation();

      if (forceExternal && (low.startsWith("http://") || low.startsWith("https://"))) {
        try {
          window.open(t, "_blank", "noopener,noreferrer");
        } catch {
          window.location.assign(t);
        }
        return;
      }

      openExternalLinkFromMiniApp(t);
    };

    root.addEventListener("click", onClickCapture, true);
    return () => root.removeEventListener("click", onClickCapture, true);
  }, [html, forceExternal]);

  return ref;
}
