import axios from "axios";
import { AlertTriangle, Loader2, MessageCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMiniAppAuthStore } from "../../store/miniAppAuthStore.js";

/**
 * Извлекает строку init_data из параметров запуска Web App мессенджера.
 *
 * Мессенджер MAX может передавать данные:
 *  - в хэше URL (например, `#tgWebAppData=...` или `#initData=...`),
 *  - в query-параметрах (`?init_data=...`),
 *  - через объект `window.MaxWebApp.initData` (если SDK внедрит его в runtime).
 *
 * Если ничего не нашли — вернём пустую строку, бэкенд отдаст 400 с понятной ошибкой.
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
    // Fallback: если весь hash — это сырая строка init_data (key=value&...).
    if (/=/.test(hash)) return hash;
  }

  // Dev-режим: позволяем прокидывать chat_id через query для локальных прогонов
  // (бэкенд пока не проверяет подпись — см. TODO в routers/miniapp.py).
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

function Spinner({ label }) {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-600/20">
        <Loader2 className="h-7 w-7 animate-spin text-emerald-400" strokeWidth={2} aria-hidden />
      </div>
      <div className="text-sm text-slate-300">{label}</div>
    </div>
  );
}

function ErrorPanel({ title, detail, onRetry }) {
  return (
    <div className="mx-auto flex h-full w-full max-w-md flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-600/20">
        <AlertTriangle className="h-7 w-7 text-red-400" strokeWidth={2} aria-hidden />
      </div>
      <div className="text-base font-semibold text-white">{title}</div>
      {detail ? <div className="text-sm text-slate-300">{detail}</div> : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded-lg border border-slate-700 bg-slate-800/80 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          Повторить
        </button>
      ) : null}
    </div>
  );
}

/**
 * Точка входа публичного Mini App: `/inn/:inn`.
 * Авторизует пользователя через `POST /api/miniapp/auth`,
 * сохраняет JWT в `useMiniAppAuthStore` и показывает заглушку приложения.
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
    return <Spinner label="Входим в приложение…" />;
  }
  if (status === "error") {
    return <ErrorPanel title={errorTitle} detail={errorDetail} onRetry={authorize} />;
  }

  const orgTitle =
    authState.organizationDisplayName || authState.organizationName || "вашу организацию";

  return (
    <div className="mx-auto flex h-full w-full max-w-md flex-col items-center justify-center gap-5 px-6 py-10 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-600/20 text-emerald-300">
        <MessageCircle className="h-8 w-8" strokeWidth={1.75} aria-hidden />
      </div>
      <div>
        <div className="text-2xl font-semibold text-white">Добро пожаловать в приложение!</div>
        <div className="mt-1 text-sm text-slate-400">
          Вы авторизованы в Mini App через {orgTitle}.
        </div>
      </div>
      <div className="w-full rounded-2xl border border-slate-800 bg-slate-900/80 p-4 text-left text-sm">
        <div className="text-xs uppercase tracking-wide text-slate-500">Ваш Chat ID</div>
        <div className="mt-1 break-all font-mono text-base text-white">{authState.chatId}</div>
        {authState.name ? (
          <>
            <div className="mt-3 text-xs uppercase tracking-wide text-slate-500">Имя</div>
            <div className="mt-1 text-base text-slate-100">{authState.name}</div>
          </>
        ) : null}
      </div>
      <p className="text-xs text-slate-500">
        Здесь будет интерфейс Mini App: магазин, запись на приём, личный кабинет пациента и т.д.
      </p>
    </div>
  );
}
