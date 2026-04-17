import { Avatar, Button, Container, Flex, Panel, Typography } from "@maxhub/max-ui";
import axios from "axios";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMiniAppAuthStore } from "../../store/miniAppAuthStore.js";
import { useMiniAppConfigStore } from "../../store/miniAppConfigStore.js";
import { useMiniAppThemeStore } from "../../store/miniAppThemeStore.js";

/**
 * Извлекает строку init_data из параметров запуска Web App мессенджера.
 */
function extractInitData(searchParams) {
  const winAny = typeof window !== "undefined" ? window : {};

  const fromWindow =
    winAny?.MaxWebApp?.initData ||
    winAny?.maxWebApp?.initData ||
    winAny?.TelegramWebApp?.initData ||
    winAny?.Telegram?.WebApp?.initData ||
    "";
  if (typeof fromWindow === "string" && fromWindow.trim()) {
    return fromWindow.trim();
  }

  const fromQuery =
    searchParams.get("init_data") ||
    searchParams.get("initData") ||
    searchParams.get("tgWebAppData") ||
    "";
  if (fromQuery) return fromQuery;

  const hash = typeof window !== "undefined" ? (window.location.hash || "").replace(/^#/, "") : "";
  if (hash) {
    const parsed = new URLSearchParams(hash);
    const h =
      parsed.get("init_data") ||
      parsed.get("initData") ||
      parsed.get("tgWebAppData") ||
      "";
    if (h) return h;
    if (/=/.test(hash)) return hash;
  }

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

function Spinner({ label }) {
  return (
    <StatusScreen>
      <Avatar size={64} aria-hidden />
      <Typography.Title level={3}>Входим в приложение…</Typography.Title>
      {label ? <Typography.Text>{label}</Typography.Text> : null}
    </StatusScreen>
  );
}

function ErrorScreen({ title, detail, onRetry }) {
  return (
    <StatusScreen>
      <Avatar size={64} aria-hidden />
      <Typography.Title level={3}>{title}</Typography.Title>
      {detail ? <Typography.Text>{detail}</Typography.Text> : null}
      {onRetry ? (
        <Button mode="primary" onClick={onRetry}>
          Повторить
        </Button>
      ) : null}
    </StatusScreen>
  );
}

/**
 * Нижняя навигация (Tabbar) по списку опубликованных страниц сайта.
 * Дизайн сделан максимально нативно: фиксированная нижняя планка, safe-area,
 * активная вкладка подсвечивается фирменным цветом через CSS-переменные MAX UI.
 */
function MiniAppTabbar({ pages, activeSlug, onChange, themeColor }) {
  if (!pages || pages.length === 0) return null;
  return (
    <nav
      aria-label="Навигация Mini App"
      style={{
        position: "sticky",
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 10,
        backdropFilter: "blur(10px)",
        background: "var(--max-color-panel-secondary, rgba(255,255,255,0.96))",
        borderTop: "1px solid var(--max-color-separator, rgba(0,0,0,0.08))",
        paddingBottom: "env(safe-area-inset-bottom, 0px)",
      }}
    >
      <Flex
        as="ul"
        justify="space-around"
        align="stretch"
        style={{ listStyle: "none", margin: 0, padding: "4px 4px 6px" }}
      >
        {pages.map((p) => {
          const active = p.slug === activeSlug;
          return (
            <li key={p.id} style={{ flex: 1, display: "flex" }}>
              <button
                type="button"
                onClick={() => onChange(p.slug)}
                aria-current={active ? "page" : undefined}
                style={{
                  flex: 1,
                  minHeight: 52,
                  padding: "6px 4px",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 2,
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  color: active
                    ? themeColor || "var(--max-color-primary, #000)"
                    : "var(--max-color-text-secondary, #6b7280)",
                  fontWeight: active ? 600 : 500,
                  fontSize: 12,
                  lineHeight: 1.2,
                  transition: "color 120ms ease",
                }}
              >
                <span
                  aria-hidden
                  style={{
                    display: "inline-block",
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: active
                      ? themeColor || "var(--max-color-primary, #000)"
                      : "transparent",
                  }}
                />
                <span
                  style={{
                    maxWidth: "100%",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {p.title}
                </span>
              </button>
            </li>
          );
        })}
      </Flex>
    </nav>
  );
}

/**
 * Шапка Mini App. Заголовок и подзаголовок — из конфига сайта, акцент — theme_color.
 */
function MiniAppHeader({ title, subtitle, logoUrl, themeColor }) {
  return (
    <Panel
      mode="primary"
      style={{
        padding: "16px",
        borderBottom: "1px solid var(--max-color-separator, rgba(0,0,0,0.08))",
        background: themeColor
          ? `linear-gradient(135deg, ${themeColor} 0%, ${themeColor}DD 100%)`
          : "var(--max-color-primary, #0f172a)",
        color: "#fff",
      }}
    >
      <Flex align="center" gap={12}>
        {logoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={logoUrl}
            alt=""
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              objectFit: "cover",
              background: "rgba(255,255,255,0.15)",
            }}
          />
        ) : (
          <Avatar size={44} aria-hidden />
        )}
        <Flex direction="column" gap={2} style={{ minWidth: 0, flex: 1 }}>
          <Typography.Title
            level={4}
            style={{
              color: "#fff",
              margin: 0,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {title || "Mini App"}
          </Typography.Title>
          {subtitle ? (
            <Typography.Caption style={{ color: "rgba(255,255,255,0.85)" }}>
              {subtitle}
            </Typography.Caption>
          ) : null}
        </Flex>
      </Flex>
    </Panel>
  );
}

/**
 * Отрисовка контента страницы (HTML/Markdown из CMS).
 *
 * Сейчас используется `dangerouslySetInnerHTML`, т.к. контент введён внутри
 * компании (не UGC) и рендерится в нативном WebView мессенджера. Если в будущем
 * появится публичное редактирование — стоит прогонять через DOMPurify.
 */
function MiniAppPageContent({ page }) {
  if (!page) {
    return (
      <Flex direction="column" align="center" gap={8} style={{ padding: 32, textAlign: "center" }}>
        <Typography.Title level={4}>Страница не выбрана</Typography.Title>
        <Typography.Text>Выберите раздел в нижнем меню.</Typography.Text>
      </Flex>
    );
  }
  return (
    <Container>
      <Flex direction="column" gap={12} style={{ padding: "16px 16px 24px" }}>
        <Typography.Title level={3}>{page.title}</Typography.Title>
        {page.content ? (
          <div
            className="miniapp-page-content"
            style={{ lineHeight: 1.55, fontSize: 15, color: "var(--max-color-text-primary, #111)" }}
            dangerouslySetInnerHTML={{ __html: page.content }}
          />
        ) : (
          <Typography.Text>Раздел пока пуст.</Typography.Text>
        )}
      </Flex>
    </Container>
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
      const firstSlug = Array.isArray(cfg?.pages) && cfg.pages.length ? cfg.pages[0].slug : null;
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

  if (status === "loading") {
    return <Spinner label="Загружаем содержимое…" />;
  }
  if (status === "error") {
    return <ErrorScreen title={errorTitle} detail={errorDetail} onRetry={bootstrap} />;
  }

  const pages = Array.isArray(config?.pages) ? config.pages : [];
  const activePage =
    pages.find((p) => p.slug === activeSlug) || (pages.length > 0 ? pages[0] : null);
  const themeColor = config?.theme_color || null;

  return (
    <Panel mode="secondary" style={{ minHeight: "100%", display: "flex", flexDirection: "column" }}>
      <MiniAppHeader
        title={config?.title}
        subtitle={config?.subtitle}
        logoUrl={config?.logo_url}
        themeColor={themeColor}
      />
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", overscrollBehavior: "contain" }}>
        {pages.length === 0 ? (
          <Flex
            direction="column"
            align="center"
            gap={8}
            style={{ padding: 32, textAlign: "center" }}
          >
            <Typography.Title level={4}>Пока нет опубликованных страниц</Typography.Title>
            <Typography.Text>
              Администратор ещё не наполнил сайт. Попробуйте позже.
            </Typography.Text>
          </Flex>
        ) : (
          <MiniAppPageContent page={activePage} />
        )}
      </div>
      <MiniAppTabbar
        pages={pages}
        activeSlug={activePage?.slug || null}
        onChange={setActiveSlug}
        themeColor={themeColor}
      />
    </Panel>
  );
}
