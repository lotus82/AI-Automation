import { MaxUI } from "@maxhub/max-ui";
import "@maxhub/max-ui/dist/styles.css";
import { useEffect, useMemo } from "react";
import { Outlet } from "react-router-dom";
import { useMiniAppThemeStore } from "../../store/miniAppThemeStore.js";
import "./miniappViewport.css";

/** Фон зоны под фиксированным Tabbar Mini App (см. MiniAppTabbar). */
const MINIAPP_TABBAR_ZONE_BG = "#f8fafc";

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
 *    expand/ready у MAX/Telegram WebApp; высота `100dvh` + `--tg-viewport-stable-height`;
 *    верхний safe-area — padding на `miniapp-root` (фон бренда), нижний — на `<main>` (фон таббара).
 *
 * Важно: провайдер и стили MAX UI подключаются ТОЛЬКО здесь — в
 * административную панель (Tailwind) они не проникают.
 */
export function MiniAppLayout() {
  const themeColor = useMiniAppThemeStore((s) => s.themeColor);
  const colorScheme = useMiniAppThemeStore((s) => s.colorScheme);

  useEffect(() => {
    const webApp =
      typeof window !== "undefined"
        ? window.WebApp || window.MaxWebApp || window.maxWebApp || window.Telegram?.WebApp
        : null;
    if (webApp) {
      if (typeof webApp.expand === "function") webApp.expand();
      if (typeof webApp.ready === "function") webApp.ready();
    }
  }, []);

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

    document.documentElement.classList.add("miniapp-viewport");
    document.body.classList.add("miniapp-viewport");
    const rootEl = document.getElementById("root");
    rootEl?.classList.add("miniapp-viewport-fill");

    return () => {
      if (prevContent !== null) {
        meta.setAttribute("content", prevContent);
      } else if (!originalViewport && meta.parentNode) {
        meta.parentNode.removeChild(meta);
      }
      document.body.style.overflow = prevBodyOverflow;
      document.body.style.overscrollBehavior = prevBodyOverscroll;
      document.documentElement.classList.remove("miniapp-viewport");
      document.body.classList.remove("miniapp-viewport");
      document.getElementById("root")?.classList.remove("miniapp-viewport-fill");
    };
  }, []);

  useEffect(() => {
    const html = document.documentElement;
    const body = document.body;
    const prevHtmlBg = html.style.backgroundColor;
    const prevBodyBg = body.style.backgroundColor;

    let meta = document.querySelector('meta[name="theme-color"]');
    const hadMetaAtStart = Boolean(meta);
    const prevThemeContent = meta?.getAttribute("content");
    let createdMeta = false;

    const accent = (themeColor || "").trim();
    html.style.backgroundColor = accent || "#ffffff";
    body.style.backgroundColor = MINIAPP_TABBAR_ZONE_BG;

    if (!meta) {
      meta = document.createElement("meta");
      meta.setAttribute("name", "theme-color");
      document.head.appendChild(meta);
      createdMeta = true;
    }
    meta.setAttribute("content", accent || "#ffffff");

    return () => {
      html.style.backgroundColor = prevHtmlBg;
      body.style.backgroundColor = prevBodyBg;
      if (createdMeta && meta?.parentNode) {
        meta.parentNode.removeChild(meta);
      } else if (hadMetaAtStart && meta) {
        if (prevThemeContent != null && prevThemeContent !== "") {
          meta.setAttribute("content", prevThemeContent);
        } else {
          meta.removeAttribute("content");
        }
      }
    };
  }, [themeColor]);

  const brandStyle = useMemo(() => buildBrandStyle(themeColor), [themeColor]);

  const accentHex = (themeColor || "").trim();
  const rootStyle = {
    background: accentHex || "#ffffff",
    display: "flex",
    flexDirection: "column",
    flex: 1,
    minHeight: 0,
    width: "100%",
    maxWidth: "100vw",
    overflow: "hidden",
    paddingTop: "env(safe-area-inset-top, 0px)",
    ...brandStyle,
  };

  // Провайдер MAX UI. Если страница явно не задала схему, не передаём prop вовсе —
  // MAX UI определит её автоматически по системной настройке устройства.
  const maxUiProps = colorScheme ? { colorScheme } : {};

  return (
    <MaxUI {...maxUiProps}>
      {/*
        Провайдер MAX UI может оборачивать дерево; внешний flex гарантирует высоту до #root.
        См. https://dev.max.ru/ui — типовая вёрстка мини-приложения на всю область WebView.
      */}
      <div
        className="miniapp-maxui-stretch"
        style={{
          flex: 1,
          minHeight: 0,
          width: "100%",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div style={rootStyle} className="miniapp-root">
          {/*
            Важно: не включаем прокрутку на <main>. Иначе вложенный flex (Panel + область контента)
            с flex:1 / minHeight:0 внутри прокручиваемого родителя даёт нулевую высоту середины —
            в WebView MAX видна только шапка и Tabbar, без текста страницы.
          */}
          <main
            style={{
              flex: 1,
              minHeight: 0,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              overscrollBehavior: "none",
              backgroundColor: MINIAPP_TABBAR_ZONE_BG,
              paddingBottom: "env(safe-area-inset-bottom, 0px)",
            }}
          >
            <Outlet />
          </main>
        </div>
      </div>
    </MaxUI>
  );
}
