import { MaxUI } from "@maxhub/max-ui";
import "@maxhub/max-ui/dist/styles.css";
import { useEffect, useMemo } from "react";
import { Outlet } from "react-router-dom";
import { useMiniAppThemeStore } from "../../store/miniAppThemeStore.js";

/**
 * HEX-цвет → RGB-строка "r, g, b" для использования в `rgba(var(--max-color-primary-rgb), …)`.
 * Поддерживает форматы `#RGB` и `#RRGGBB`; в остальных случаях возвращает null.
 */
function hexToRgbString(hex) {
  if (typeof hex !== "string") return null;
  const s = hex.trim().replace(/^#/, "");
  if (!/^[0-9a-fA-F]{3}$/.test(s) && !/^[0-9a-fA-F]{6}$/.test(s)) return null;
  const full = s.length === 3 ? s.split("").map((c) => c + c).join("") : s;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `${r}, ${g}, ${b}`;
}

/**
 * Собирает inline-style с CSS-переменными бренда. Переопределяем несколько токенов
 * MAX UI, отвечающих за акцент, — чтобы работало независимо от точного имени
 * переменной в конкретной версии дизайн-системы (см. https://dev.max.ru/ui,
 * раздел «Кастомизация компонентов»).
 *
 * Если токен не был указан (null) — возвращаем пустой style, MAX UI применит
 * свои нативные дефолты (iOS/Android).
 */
function buildBrandStyle(themeColor) {
  if (!themeColor) return {};
  const rgb = hexToRgbString(themeColor);
  /** @type {Record<string, string>} */
  const style = {
    "--max-color-primary": themeColor,
    "--max-color-accent": themeColor,
    "--max-color-brand": themeColor,
    "--max-color-link": themeColor,
    "--max-color-primary-hover": themeColor,
  };
  if (rgb) {
    style["--max-color-primary-rgb"] = rgb;
    style["--max-color-accent-rgb"] = rgb;
  }
  return style;
}

/**
 * Полноэкранный каркас Mini App для мессенджера MAX.
 *
 * Что делает:
 *  - Оборачивает публичные страницы в провайдер `<MaxUI>` и подключает стили
 *    дизайн-системы MAX (`@maxhub/max-ui/dist/styles.css`).
 *  - Определяет `colorScheme` (light/dark): если страница сайта задала явно —
 *    передаётся в провайдер; иначе — автоопределение MAX UI.
 *  - Динамически брендирует акцентный цвет через CSS-переменные на корневом
 *    элементе — `theme_color` приходит из конструктора сайтов.
 *  - Оптимизирует мобильный WebView: viewport без зума, блокировка overscroll,
 *    safe-area padding.
 *
 * Важно: провайдер и стили MAX UI подключаются ТОЛЬКО здесь — в
 * административную панель (Tailwind) они не проникают.
 */
export function MiniAppLayout() {
  const themeColor = useMiniAppThemeStore((s) => s.themeColor);
  const colorScheme = useMiniAppThemeStore((s) => s.colorScheme);

  useEffect(() => {
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

  const brandStyle = useMemo(() => buildBrandStyle(themeColor), [themeColor]);

  const rootStyle = {
    height: "100dvh",
    width: "100vw",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    paddingTop: "env(safe-area-inset-top, 0px)",
    paddingBottom: "env(safe-area-inset-bottom, 0px)",
    paddingLeft: "env(safe-area-inset-left, 0px)",
    paddingRight: "env(safe-area-inset-right, 0px)",
    ...brandStyle,
  };

  // Провайдер MAX UI. Если страница явно не задала схему, не передаём prop вовсе —
  // MAX UI определит её автоматически по системной настройке устройства.
  const maxUiProps = colorScheme ? { colorScheme } : {};

  return (
    <MaxUI {...maxUiProps}>
      <div style={rootStyle} className="miniapp-root">
        <main style={{ flex: 1, minHeight: 0, overflowY: "auto", overscrollBehavior: "contain" }}>
          <Outlet />
        </main>
      </div>
    </MaxUI>
  );
}
