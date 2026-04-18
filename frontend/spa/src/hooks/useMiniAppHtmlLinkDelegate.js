import { useEffect, useRef } from "react";

/**
 * В WebView Mini App клики по <a href="sberbankonline://…"> и другим не-http(s) схемам
 * часто не срабатывают. Перехватываем в capture и открываем через location.assign.
 */
function shouldDelegateNavigation(href) {
  if (!href || href.startsWith("#")) return false;
  const t = href.trim();
  if (/^javascript:/i.test(t)) return false;
  const low = t.toLowerCase();
  if (low.startsWith("http://") || low.startsWith("https://")) return false;
  if (low.startsWith("mailto:") || low.startsWith("tel:") || low.startsWith("sms:")) return false;
  return /^[a-z][a-z0-9+.-]*:/i.test(t);
}

/**
 * @param {string | undefined} html — при смене контента перевешиваем обработчик
 * @returns {React.RefObject<HTMLDivElement | null>}
 */
export function useMiniAppHtmlLinkDelegate(html) {
  const ref = useRef(null);

  useEffect(() => {
    const root = ref.current;
    if (!root) return undefined;

    const onClickCapture = (e) => {
      if (!(e.target instanceof Element)) return;
      const anchor = e.target.closest("a[href]");
      if (!anchor || !root.contains(anchor)) return;
      const href = anchor.getAttribute("href");
      if (!href || !shouldDelegateNavigation(href)) return;
      e.preventDefault();
      e.stopPropagation();
      window.location.assign(href);
    };

    root.addEventListener("click", onClickCapture, true);
    return () => root.removeEventListener("click", onClickCapture, true);
  }, [html]);

  return ref;
}
