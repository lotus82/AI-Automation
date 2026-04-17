import { Avatar, Button, Container, Flex, Panel, Typography } from "@maxhub/max-ui";
import axios from "axios";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMiniAppAuthStore } from "../../store/miniAppAuthStore.js";

/**
 * Извлекает строку init_data из параметров запуска Web App мессенджера.
 *
 * Мессенджер MAX может передавать данные:
 *  - в хэше URL (`#initData=...` / `#tgWebAppData=...`),
 *  - в query-параметрах (`?init_data=...`),
 *  - через `window.MaxWebApp.initData` (если SDK внедрит).
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

/** Центрированный статусный экран (загрузка/ошибка/успех) в стиле MAX UI. */
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
 * Точка входа публичного Mini App: `/inn/:inn`.
 * Авторизует пользователя через `POST /api/miniapp/auth`,
 * сохраняет JWT в `useMiniAppAuthStore`. UI собран на компонентах MAX UI,
 * чтобы визуально быть неотличимым от нативных элементов мессенджера.
 */
export function MiniAppEntryPage() {
  const { inn } = useParams();
  const [searchParams] = useSearchParams();
  const setAuth = useMiniAppAuthStore((s) => s.setAuth);
  const clearAuth = useMiniAppAuthStore((s) => s.clearAuth);
  const authState = useMiniAppAuthStore((s) => ({
    token: s.token,
    chatId: s.chatId,
    name: s.name,
    organizationName: s.organizationName,
    organizationDisplayName: s.organizationDisplayName,
  }));

  const [status, setStatus] = useState("loading");
  const [errorTitle, setErrorTitle] = useState("");
  const [errorDetail, setErrorDetail] = useState("");
  const startedRef = useRef(false);

  const initData = useMemo(() => extractInitData(searchParams), [searchParams]);

  const authorize = useCallback(async () => {
    setStatus("loading");
    setErrorTitle("");
    setErrorDetail("");

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
      const { data } = await axios.post("/api/miniapp/auth", {
        inn: String(inn).trim(),
        init_data: initData,
      });
      setAuth({
        token: data.access_token,
        userId: data.user_id,
        organizationId: data.organization_id,
        chatId: data.chat_id,
        name: data.name,
      });
      try {
        const meResp = await axios.get("/api/miniapp/me", {
          headers: { Authorization: `Bearer ${data.access_token}` },
        });
        setAuth({
          token: data.access_token,
          userId: data.user_id,
          organizationId: data.organization_id,
          chatId: data.chat_id,
          name: meResp.data?.name ?? data.name,
          organizationName: meResp.data?.organization_name,
          organizationDisplayName: meResp.data?.organization_display_name,
        });
      } catch {
        // /me — не критично для старта, но без него не покажем название организации.
      }
      setStatus("ready");
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
    }
  }, [inn, initData, setAuth, clearAuth]);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    authorize();
  }, [authorize]);

  if (status === "loading") {
    return <Spinner label="Пожалуйста, подождите…" />;
  }
  if (status === "error") {
    return <ErrorScreen title={errorTitle} detail={errorDetail} onRetry={authorize} />;
  }

  const orgTitle =
    authState.organizationDisplayName || authState.organizationName || "вашу организацию";

  return (
    <Panel mode="secondary" style={{ minHeight: "100%" }}>
      <Container>
        <Flex
          direction="column"
          gap={20}
          style={{ padding: "24px 16px 40px", minHeight: "100dvh" }}
        >
          <Flex direction="column" align="center" gap={12} style={{ textAlign: "center" }}>
            <Avatar size={72} aria-label={authState.name || "Mini App"} />
            <Typography.Title level={2}>Добро пожаловать!</Typography.Title>
            <Typography.Text>
              Вы авторизованы в Mini App через {orgTitle}.
            </Typography.Text>
          </Flex>

          <Panel mode="primary" style={{ padding: 16, borderRadius: 16 }}>
            <Flex direction="column" gap={12}>
              <Flex direction="column" gap={2}>
                <Typography.Caption>Chat ID</Typography.Caption>
                <Typography.Text style={{ wordBreak: "break-all", fontFamily: "ui-monospace, monospace" }}>
                  {authState.chatId}
                </Typography.Text>
              </Flex>
              {authState.name ? (
                <Flex direction="column" gap={2}>
                  <Typography.Caption>Имя</Typography.Caption>
                  <Typography.Text>{authState.name}</Typography.Text>
                </Flex>
              ) : null}
            </Flex>
          </Panel>

          <Flex direction="column" gap={8} style={{ textAlign: "center" }}>
            <Typography.Footnote>
              Здесь появится интерфейс Mini App: магазин, запись на приём, личный кабинет и т.д.
            </Typography.Footnote>
          </Flex>
        </Flex>
      </Container>
    </Panel>
  );
}
