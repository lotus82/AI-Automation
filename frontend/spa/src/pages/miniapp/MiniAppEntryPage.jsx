import { Button, Container, Flex, Panel, Spinner, Typography } from "@maxhub/max-ui";
import axios from "axios";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMiniAppAuthStore } from "../../store/miniAppAuthStore.js";
import { useMiniAppConfigStore } from "../../store/miniAppConfigStore.js";
import { useMiniAppThemeStore } from "../../store/miniAppThemeStore.js";
import { normalizeSiteLogoUrl } from "../../utils/siteLogoUrl.js";
import "./miniappPageContent.css";

/**
 * Извлекает строку ``init_data`` из параметров запуска Mini App мессенджера MAX.
 *
 * Согласно документации MAX (https://dev.max.ru/docs/webapps/validation) стартовые
 * параметры передаются в URL-фрагменте в поле ``WebAppData``:
 *
 *     https://example.com/inn/1234#WebAppData=<urlencoded>&WebAppPlatform=web&WebAppVersion=26.2.8
 *
 * Клиент обязан передать на бэкенд ИМЕННО содержимое ``WebAppData`` (один раз URL-
 * декодированное — это автоматически делает ``URLSearchParams.get``). Именно по этой
 * строке бэкенд считает HMAC-SHA256 и проверяет поле ``hash``.
 *
 * Порядок поиска (в порядке приоритета):
 *   1. ``window.WebApp.initData`` — официальный MAX Bridge; содержит уже готовую
 *      строку ``WebAppData``.
 *   2. URL-фрагмент (``window.location.hash``), ключ ``WebAppData``.
 *   3. Совместимость с Telegram-стилем (``tgWebAppData``/``initData``) и явный
 *      query-param ``?init_data=…`` — пригодится для E2E тестов и прежних клиентов.
 *   4. Dev-fallback ``?chat_id=…`` для браузерной отладки (подпись будет невалидна —
 *      бэкенд отдаст 401/403, но это ожидаемо вне мессенджера).
 */
function extractInitData(searchParams) {
  const winAny = typeof window !== "undefined" ? window : {};

  const fromMaxBridge =
    winAny?.WebApp?.initData ||
    winAny?.MaxWebApp?.initData ||
    winAny?.maxWebApp?.initData ||
    winAny?.TelegramWebApp?.initData ||
    winAny?.Telegram?.WebApp?.initData ||
    "";
  if (typeof fromMaxBridge === "string" && fromMaxBridge.trim()) {
    return fromMaxBridge.trim();
  }

  const rawHash =
    typeof window !== "undefined" ? (window.location.hash || "").replace(/^#/, "") : "";
  if (rawHash) {
    let hashParams = null;
    try {
      hashParams = new URLSearchParams(rawHash);
    } catch {
      hashParams = null;
    }
    if (hashParams) {
      const webAppData = hashParams.get("WebAppData");
      if (webAppData && webAppData.trim()) return webAppData.trim();
      const tgLike =
        hashParams.get("tgWebAppData") ||
        hashParams.get("initData") ||
        hashParams.get("init_data") ||
        "";
      if (tgLike && tgLike.trim()) return tgLike.trim();
    }
    if (/=/.test(rawHash) && /\bhash=/.test(rawHash)) {
      return rawHash;
    }
  }

  const fromQuery =
    searchParams.get("init_data") ||
    searchParams.get("initData") ||
    searchParams.get("tgWebAppData") ||
    searchParams.get("WebAppData") ||
    "";
  if (fromQuery) return fromQuery;

  const devChatId = searchParams.get("chat_id");
  if (devChatId) {
    const name = searchParams.get("name") || "";
    const params = new URLSearchParams();
    params.set("chat_id", devChatId);
    if (name) params.set("name", name);
    return params.toString();
  }
  return "";
}

/** HEX → rgba() для полупрозрачных кнопок меню. */
function hexToRgba(hex, alpha) {
  if (typeof hex !== "string" || alpha < 0 || alpha > 1) return `rgba(99, 102, 241, ${alpha})`;
  const s = hex.trim().replace(/^#/, "");
  if (!/^[0-9a-fA-F]{3}$/.test(s) && !/^[0-9a-fA-F]{6}$/.test(s)) return `rgba(99, 102, 241, ${alpha})`;
  const full = s.length === 3 ? s.split("").map((c) => c + c).join("") : s;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function StatusScreen({ children }) {
  return (
    <Panel mode="secondary" style={{ minHeight: "100%" }}>
      <Container>
        <Flex
          direction="column"
          align="center"
          justify="center"
          gap={16}
          style={{ minHeight: "100dvh", padding: "32px 16px", textAlign: "center" }}
        >
          {children}
        </Flex>
      </Container>
    </Panel>
  );
}

function LoadingScreen({ label }) {
  return (
    <StatusScreen>
      <Spinner size="large" />
      <Typography.Title>Входим в приложение…</Typography.Title>
      {label ? <Typography.Body>{label}</Typography.Body> : null}
    </StatusScreen>
  );
}

function ErrorScreen({ title, detail, onRetry }) {
  return (
    <StatusScreen>
      <Typography.Title>{title}</Typography.Title>
      {detail ? <Typography.Body>{detail}</Typography.Body> : null}
      {onRetry ? (
        <Button mode="primary" onClick={onRetry}>
          Повторить
        </Button>
      ) : null}
    </StatusScreen>
  );
}

/**
 * Нижняя навигация: сегментированные «кнопки» (чипы) с акцентом бренда.
 */
function MiniAppTabbar({ items, activeSlug, onChange, themeColor }) {
  if (!items || items.length === 0) return null;
  const accent = themeColor && themeColor.trim() ? themeColor.trim() : "#4f46e5";
  return (
    <nav
      aria-label="Навигация Mini App"
      style={{
        flexShrink: 0,
        flexGrow: 0,
        zIndex: 10,
        backdropFilter: "blur(12px)",
        background: "linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(248,250,252,0.98) 100%)",
        borderTop: "1px solid rgba(15, 23, 42, 0.08)",
        boxShadow: "0 -4px 24px rgba(15, 23, 42, 0.06)",
        paddingTop: 10,
        paddingLeft: 12,
        paddingRight: 12,
        paddingBottom: "calc(10px + env(safe-area-inset-bottom, 0px))",
      }}
    >
      <ul
        style={{
          display: "flex",
          flexWrap: "wrap",
          listStyle: "none",
          listStyleType: "none",
          margin: 0,
          padding: 0,
          gap: 8,
          justifyContent: "center",
          alignItems: "stretch",
        }}
        className="miniapp-tabbar-scroll"
      >
        {items.map((item) => {
          const active = item.slug === activeSlug;
          return (
            <li
              key={item.slug}
              style={{
                flex: "1 1 auto",
                minWidth: "min(100%, 7.5rem)",
                maxWidth: "100%",
                listStyle: "none",
                listStyleType: "none",
              }}
            >
              <button
                type="button"
                onClick={() => onChange(item.slug)}
                aria-current={active ? "page" : undefined}
                style={{
                  width: "100%",
                  minHeight: 44,
                  padding: "10px 14px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  borderRadius: 14,
                  border: active
                    ? `1.5px solid ${hexToRgba(accent, 0.55)}`
                    : "1.5px solid rgba(15, 23, 42, 0.1)",
                  background: active ? hexToRgba(accent, 0.16) : "rgba(255, 255, 255, 0.9)",
                  color: active ? accent : "#475569",
                  fontWeight: active ? 700 : 600,
                  fontSize: 13,
                  lineHeight: 1.3,
                  letterSpacing: active ? "-0.01em" : "0",
                  boxShadow: active
                    ? `0 2px 8px ${hexToRgba(accent, 0.22)}, inset 0 1px 0 rgba(255,255,255,0.85)`
                    : "0 1px 3px rgba(15, 23, 42, 0.07), inset 0 1px 0 rgba(255,255,255,0.95)",
                  transition: "background 0.18s ease, color 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease, transform 0.12s ease",
                  WebkitTapHighlightColor: "transparent",
                }}
              >
                <span
                  style={{
                    textAlign: "center",
                    whiteSpace: "normal",
                    overflowWrap: "anywhere",
                    wordBreak: "break-word",
                  }}
                >
                  {item.label}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/**
 * Шапка Mini App. Заголовок и подзаголовок — из конфига сайта, акцент — theme_color.
 */
function MiniAppHeader({ title, subtitle, logoUrl, themeColor }) {
  const logoSrc = useMemo(() => normalizeSiteLogoUrl(logoUrl), [logoUrl]);
  const [logoBroken, setLogoBroken] = useState(false);
  useEffect(() => {
    setLogoBroken(false);
  }, [logoSrc]);

  const background = themeColor
    ? `linear-gradient(135deg, ${themeColor} 0%, ${themeColor}DD 100%)`
    : "var(--max-color-primary, #0f172a)";
  /* Обычный header вместо Panel: у Panel в max-ui часто flex-grow:1 — шапка съедала весь экран. */
  return (
    <header
      style={{
        flexShrink: 0,
        flexGrow: 0,
        boxSizing: "border-box",
        padding: "16px",
        borderBottom: "1px solid rgba(0,0,0,0.08)",
        background,
        color: "#fff",
      }}
    >
      <Flex align="center" gap={12}>
        {logoSrc && !logoBroken ? (
          <img
            src={logoSrc}
            alt=""
            onError={() => setLogoBroken(true)}
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              objectFit: "cover",
              background: "rgba(255,255,255,0.15)",
            }}
          />
        ) : (
          <div
            aria-hidden
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: "rgba(255,255,255,0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 20,
              fontWeight: 600,
              color: "#fff",
            }}
          >
            {(title || "M").slice(0, 1).toUpperCase()}
          </div>
        )}
        <Flex direction="column" gap={2} style={{ minWidth: 0, flex: 1 }}>
          <div
            style={{
              color: "#fff",
              margin: 0,
              fontSize: 18,
              fontWeight: 600,
              lineHeight: 1.25,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {title || "Mini App"}
          </div>
          {subtitle ? (
            <div style={{ color: "rgba(255,255,255,0.9)", fontSize: 13, lineHeight: 1.35 }}>
              {subtitle}
            </div>
          ) : null}
        </Flex>
      </Flex>
    </header>
  );
}

/**
 * Отрисовка контента страницы (HTML/Markdown из CMS).
 *
 * Сейчас используется `dangerouslySetInnerHTML`, т.к. контент вводят внутри
 * компании (не UGC) и рендерится в нативном WebView мессенджера. Если позже
 * появится публичное редактирование — прогнать через DOMPurify.
 */
function MiniAppPageContent({ page }) {
  if (!page) {
    return (
      <div style={{ padding: "32px 16px", textAlign: "center" }}>
        <Typography.Title>Страница не выбрана</Typography.Title>
        <div style={{ marginTop: 8 }}>
          <Typography.Body>Выберите раздел в нижнем меню.</Typography.Body>
        </div>
      </div>
    );
  }
  return (
    <div style={{ padding: "16px 16px 24px" }}>
      {/*
        Не используем Typography.Title для заголовка страницы: в MAX UI это часто
        «display»-уровень и тянет accent (theme_color), визуально перекрывая контент.
      */}
      <h2
        style={{
          margin: "0 0 12px",
          fontSize: 20,
          fontWeight: 600,
          lineHeight: 1.3,
          color: "#111827",
        }}
      >
        {(page.title || "").trim() || "Страница"}
      </h2>
      {page.content ? (
        <div
          className="miniapp-page-content"
          style={{
            lineHeight: 1.55,
            fontSize: 15,
            color: "#1f2937",
          }}
          dangerouslySetInnerHTML={{ __html: page.content }}
        />
      ) : (
        <p style={{ margin: 0, fontSize: 15, color: "#6b7280" }}>Раздел пока пуст.</p>
      )}
    </div>
  );
}

/**
 * Точка входа публичного Mini App (`/inn/:inn`):
 *  1) авторизует по `chat_id` (POST /api/miniapp/auth),
 *  2) подтягивает конфиг сайта (GET /api/public/miniapp/config/{inn}),
 *  3) применяет `theme_color` через `useMiniAppThemeStore` (CSS-переменные),
 *  4) рендерит активную страницу + нижнее меню (Tabbar).
 */
export function MiniAppEntryPage() {
  const { inn } = useParams();
  const [searchParams] = useSearchParams();
  const setAuth = useMiniAppAuthStore((s) => s.setAuth);
  const clearAuth = useMiniAppAuthStore((s) => s.clearAuth);

  const config = useMiniAppConfigStore((s) => s.config);
  const setConfig = useMiniAppConfigStore((s) => s.setConfig);
  const resetConfig = useMiniAppConfigStore((s) => s.reset);

  const setThemeColor = useMiniAppThemeStore((s) => s.setThemeColor);

  const [status, setStatus] = useState("loading");
  const [errorTitle, setErrorTitle] = useState("");
  const [errorDetail, setErrorDetail] = useState("");
  const [activeSlug, setActiveSlug] = useState(null);
  const startedRef = useRef(false);

  const initData = useMemo(() => extractInitData(searchParams), [searchParams]);

  const bootstrap = useCallback(async () => {
    setStatus("loading");
    setErrorTitle("");
    setErrorDetail("");
    resetConfig();
    setThemeColor(null);

    if (!inn || !String(inn).trim()) {
      setStatus("error");
      setErrorTitle("ИНН организации не указан в ссылке");
      setErrorDetail("Откройте Mini App по ссылке вида https://lotus-it.ru/inn/<ИНН>.");
      return;
    }
    if (!initData) {
      setStatus("error");
      setErrorTitle("Не удалось прочитать данные авторизации мессенджера");
      setErrorDetail(
        "Откройте приложение из бота MAX (кнопка Web App). Параметры запуска должны включать chat_id.",
      );
      return;
    }

    try {
      const { data: authData } = await axios.post("/api/miniapp/auth", {
        inn: String(inn).trim(),
        init_data: initData,
      });
      setAuth({
        token: authData.access_token,
        userId: authData.user_id,
        organizationId: authData.organization_id,
        chatId: authData.chat_id,
        name: authData.name,
      });
    } catch (e) {
      clearAuth();
      setStatus("error");
      const detail = e?.response?.data?.detail || e?.message || "Неизвестная ошибка";
      if (e?.response?.status === 404) {
        setErrorTitle("Организация не найдена");
      } else if (e?.response?.status === 401) {
        setErrorTitle("Не удалось подтвердить данные авторизации");
      } else {
        setErrorTitle("Не удалось войти в Mini App");
      }
      setErrorDetail(typeof detail === "string" ? detail : JSON.stringify(detail));
      return;
    }

    try {
      const { data: cfg } = await axios.get(
        `/api/public/miniapp/config/${encodeURIComponent(String(inn).trim())}`,
      );
      setConfig(cfg);
      if (cfg?.theme_color) setThemeColor(cfg.theme_color);
      const pgs = Array.isArray(cfg?.pages) ? cfg.pages : [];
      const nav =
        Array.isArray(cfg?.nav_items) && cfg.nav_items.length > 0
          ? cfg.nav_items.filter((x) => x && x.slug)
          : pgs.map((p) => ({ label: p.title, slug: p.slug }));
      const firstSlug = nav[0]?.slug ?? pgs[0]?.slug ?? null;
      setActiveSlug(firstSlug);
      setStatus("ready");
    } catch (e) {
      setStatus("error");
      const detail = e?.response?.data?.detail || e?.message || "Неизвестная ошибка";
      if (e?.response?.status === 404) {
        setErrorTitle("Контент Mini App ещё не настроен");
      } else {
        setErrorTitle("Не удалось загрузить контент Mini App");
      }
      setErrorDetail(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
  }, [inn, initData, setAuth, clearAuth, setConfig, resetConfig, setThemeColor]);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    return () => {
      setThemeColor(null);
    };
  }, [setThemeColor]);

  // Важно: хуки только до любых return — иначе при смене status (loading → ready)
  // меняется число вызовов useMemo и React падает (часто — пустой тёмный экран в WebView).
  const pages = useMemo(
    () => (Array.isArray(config?.pages) ? config.pages : []),
    [config?.pages],
  );

  const navItems = useMemo(() => {
    const raw = config?.nav_items;
    if (Array.isArray(raw) && raw.length > 0) {
      return raw.filter((x) => x && x.slug);
    }
    return pages.map((p) => ({ label: p.title, slug: p.slug }));
  }, [config?.nav_items, pages]);

  if (status === "loading") {
    return <LoadingScreen label="Загружаем содержимое…" />;
  }
  if (status === "error") {
    return <ErrorScreen title={errorTitle} detail={errorDetail} onRetry={bootstrap} />;
  }

  const activePage =
    pages.find((p) => p.slug === activeSlug) || (pages.length > 0 ? pages[0] : null);
  const themeColor = config?.theme_color || null;

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        width: "100%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        alignItems: "stretch",
        background: "var(--max-color-bg-secondary, #f3f4f6)",
      }}
    >
      <MiniAppHeader
        title={config?.title}
        subtitle={config?.subtitle}
        logoUrl={config?.logo_url}
        themeColor={themeColor}
      />
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          overscrollBehavior: "contain",
          WebkitOverflowScrolling: "touch",
          /* Явный светлый фон: в dark-схеме MAX UI иначе тело страницы может быть невидимо */
          background: "#ffffff",
          color: "#111827",
        }}
      >
        {pages.length === 0 ? (
          <Flex
            direction="column"
            align="center"
            gap={8}
            style={{ padding: 32, textAlign: "center" }}
          >
            <Typography.Title>Пока нет опубликованных страниц</Typography.Title>
            <Typography.Body>
              Администратор ещё не наполнил сайт. Попробуйте позже.
            </Typography.Body>
          </Flex>
        ) : (
          <MiniAppPageContent page={activePage} />
        )}
      </div>
      <MiniAppTabbar
        items={navItems}
        activeSlug={activePage?.slug || null}
        onChange={setActiveSlug}
        themeColor={themeColor}
      />
    </div>
  );
}
