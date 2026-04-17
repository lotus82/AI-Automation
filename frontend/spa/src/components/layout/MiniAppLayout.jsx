import { useEffect } from "react";
import { Outlet } from "react-router-dom";

/**
 * Полноэкранный каркас Mini App для мессенджера MAX.
 *
 * Отличия от корпоративной панели:
 * - Без Sidebar/Header портала — только контент на 100dvh × 100vw.
 * - Для мобильного WebView: отключение user-scalable (viewport meta),
 *   блокировка overscroll / horizontal scroll, safe-area padding.
 */
export function MiniAppLayout() {
  useEffect(() => {
    // Блокируем зум пальцами и задаём плотный мобильный viewport для WebView мессенджера.
    const originalViewport = document.querySelector('meta[name="viewport"]');
    const prevContent = originalViewport?.getAttribute("content") || null;
    const meta = originalViewport ?? document.createElement("meta");
    if (!originalViewport) {
      meta.setAttribute("name", "viewport");
      document.head.appendChild(meta);
    }
    meta.setAttribute(
      "content",
      "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover",
    );

    // Отключаем горизонтальный скролл и «резинку» на уровне body (для Safari/Android WebView).
    const prevBodyOverflow = document.body.style.overflow;
    const prevBodyOverscroll = document.body.style.overscrollBehavior;
    document.body.style.overflow = "hidden";
    document.body.style.overscrollBehavior = "none";

    return () => {
      if (prevContent !== null) {
        meta.setAttribute("content", prevContent);
      } else if (!originalViewport && meta.parentNode) {
        meta.parentNode.removeChild(meta);
      }
      document.body.style.overflow = prevBodyOverflow;
      document.body.style.overscrollBehavior = prevBodyOverscroll;
    };
  }, []);

  return (
    <div
      className="flex min-h-[100dvh] w-[100vw] flex-col overflow-hidden bg-slate-950 text-slate-100 antialiased"
      style={{
        height: "100dvh",
        paddingTop: "env(safe-area-inset-top, 0px)",
        paddingBottom: "env(safe-area-inset-bottom, 0px)",
        paddingLeft: "env(safe-area-inset-left, 0px)",
        paddingRight: "env(safe-area-inset-right, 0px)",
      }}
    >
      <main className="flex-1 overflow-y-auto overscroll-contain">
        <Outlet />
      </main>
    </div>
  );
}
