import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation } from "react-router-dom";
import { ExternalLink, Plug, Plus, RefreshCcw, Save } from "lucide-react";
import { IconDeleteButton, IconEditButton } from "../components/ui/IconActionButtons.jsx";
import api from "../api/client.js";
import { AgentChat } from "../components/Chat/AgentChat.jsx";
import { IntegrationForm } from "../components/integrations/IntegrationForm.jsx";
import { VoiceTelephonyTestPanel } from "../components/telephony/VoiceTelephonyTestPanel.jsx";
import { SK } from "../constants/systemSettingsKeys.js";
import { hintForSecretRow, mapFromList, parseTruthy } from "../utils/systemSettingsForm.js";
import { BTN_SAVE, ICON_BTN, PAGE_H1, PAGE_HEADER_BETWEEN, PAGE_TEXT, PAGE_TITLE_ICON } from "../styles/pageLayout.js";
import { formatDateTimeRu } from "../utils/dateTimeFormat.js";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const DEFAULT_MAX_GREETING =
  "Здравствуйте! Это ИИ-помощник компании. Слушаю вас.";

/** Как `max_api_base` / `MAX_API_BASE` на бэкенде — см. `src/core/config.py`, `MaxMessengerClient`. */
const MAX_INTEGRATION_BASE_URL = "https://api.max.ru";
/** Long poll `GET /updates` идёт на platform API, см. `max_platform_api_base` / `MAX_PLATFORM_API_BASE`. */
const MAX_PLATFORM_API_BASE_DEFAULT = "https://platform-api.max.ru";

function formatApiDetail(err) {
  const body = err?.response?.data;
  const status = err?.response?.status;
  const det = body?.detail;
  if (typeof det === "string") return det;
  if (Array.isArray(det)) {
    return det
      .map((x) => (typeof x === "object" && x != null ? x.msg ?? x : x))
      .join("; ");
  }
  if (det != null) return JSON.stringify(det);
  if (status) return `Ошибка ${status}`;
  return err?.message ?? String(err);
}

function initialMaxForm() {
  return {
    maxBotToken: "",
    maxBotHint: "",
    maxUsePolling: true,
    maxVoiceReply: false,
    maxCallAnswerDelay: "6",
    maxCallGreeting: DEFAULT_MAX_GREETING,
    maxBotUsername: "",
  };
}

function buildMaxFormFromMap(map) {
  let delay = 6;
  const mcad = map[SK.MAX_CALL_ANSWER_DELAY];
  if (mcad && mcad.value != null && String(mcad.value).trim() !== "") {
    const parsedD = parseInt(String(mcad.value).trim(), 10);
    if (!Number.isNaN(parsedD)) delay = parsedD;
  }
  delay = Math.max(0, Math.min(120, delay));

  const mcg = map[SK.MAX_CALL_GREETING_PHRASE];

  return {
    maxBotToken: "",
    maxBotHint: hintForSecretRow(map[SK.MAX_BOT_TOKEN]),
    maxUsePolling: parseTruthy(map[SK.MAX_USE_POLLING]?.value, true),
    maxVoiceReply: parseTruthy(map[SK.MAX_VOICE_REPLY_ENABLED]?.value, false),
    maxCallAnswerDelay: String(delay),
    maxCallGreeting:
      mcg && mcg.value != null ? String(mcg.value) : DEFAULT_MAX_GREETING,
    maxBotUsername:
      map[SK.MAX_BOT_USERNAME]?.value != null
        ? String(map[SK.MAX_BOT_USERNAME].value)
        : "",
  };
}

function collectMaxPayload(maxForm) {
  const values = {};
  values[SK.MAX_USE_POLLING] = maxForm.maxUsePolling ? "1" : "0";
  values[SK.MAX_VOICE_REPLY_ENABLED] = maxForm.maxVoiceReply ? "1" : "0";

  let dlim = parseInt(maxForm.maxCallAnswerDelay, 10);
  if (Number.isNaN(dlim)) dlim = 6;
  dlim = Math.max(0, Math.min(120, dlim));
  values[SK.MAX_CALL_ANSWER_DELAY] = String(dlim);

  values[SK.MAX_CALL_GREETING_PHRASE] = maxForm.maxCallGreeting;
  values[SK.MAX_BOT_USERNAME] = maxForm.maxBotUsername.trim();

  if (maxForm.maxBotToken.trim()) {
    values[SK.MAX_BOT_TOKEN] = maxForm.maxBotToken.trim();
  }
  return values;
}

function initialTelegramForm() {
  return { telegramToken: "", telegramHint: "" };
}

function buildTelegramFormFromMap(map) {
  return {
    telegramToken: "",
    telegramHint: hintForSecretRow(map[SK.TELEGRAM_BOT_TOKEN]),
  };
}

function collectTelegramPayload(tgForm) {
  const values = {};
  if (tgForm.telegramToken.trim()) {
    values[SK.TELEGRAM_BOT_TOKEN] = tgForm.telegramToken.trim();
  }
  return values;
}

function mapParamTypeForApi(t) {
  if (t === "integer" || t === "number") return "number";
  if (t === "boolean") return "boolean";
  return "string";
}

function buildIntegrationCreatePayload(data) {
  return {
    name: data.name,
    base_url: data.base_url,
    auth: data.auth,
    webhooks: [],
    actions: (data.actions || []).map((a) => ({
      ...a,
      parameters: (a.parameters || []).map((p) => ({
        ...p,
        type: mapParamTypeForApi(p.type),
      })),
    })),
  };
}

function mapApiRowToForm(data) {
  if (!data) return null;
  return {
    name: data.name || "",
    base_url: data.base_url != null ? String(data.base_url) : "",
    auth: data.auth && typeof data.auth === "object" ? { ...data.auth } : { auth_type: "NO_AUTH" },
    actions: Array.isArray(data.actions) ? data.actions.map((a) => ({ ...a })) : [],
  };
}

export function IntegrationsPage() {
  const location = useLocation();

  const [rows, setRows] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listErr, setListErr] = useState("");

  const [builderOpen, setBuilderOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editSource, setEditSource] = useState(null);
  const [formInitial, setFormInitial] = useState(null);
  const [editFormLoading, setEditFormLoading] = useState(false);
  const [builderErr, setBuilderErr] = useState("");
  const [integrationSaving, setIntegrationSaving] = useState(false);

  const [maxForm, setMaxForm] = useState(initialMaxForm);
  const [telegramForm, setTelegramForm] = useState(initialTelegramForm);
  const [messengerLoading, setMessengerLoading] = useState(true);
  const [messengerLoadError, setMessengerLoadError] = useState("");

  const [maxSaving, setMaxSaving] = useState(false);
  const [maxStatusMsg, setMaxStatusMsg] = useState("");
  const [maxStatusError, setMaxStatusError] = useState(false);

  const [telegramSaving, setTelegramSaving] = useState(false);
  const [telegramStatusMsg, setTelegramStatusMsg] = useState("");
  const [telegramStatusError, setTelegramStatusError] = useState(false);

  const loadList = useCallback(async () => {
    setListLoading(true);
    setListErr("");
    try {
      const { data } = await api.get("/v1/integrations");
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error(e);
      setListErr(formatApiDetail(e) || "Не удалось загрузить список интеграций");
      setRows([]);
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    const hash = location.hash?.replace(/^#/, "");
    if (!hash) return;
    const t = window.setTimeout(() => {
      document.getElementById(hash)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
    return () => window.clearTimeout(t);
  }, [location.hash, location.key]);

  const loadMessengerSettings = useCallback(async () => {
    setMessengerLoadError("");
    try {
      const { data: srows } = await api.get("/settings");
      const map = mapFromList(srows);
      setMaxForm(buildMaxFormFromMap(map));
      setTelegramForm(buildTelegramFormFromMap(map));
    } catch (e) {
      console.error(e);
      const msg = e?.response?.data?.detail ?? e?.message ?? String(e);
      setMessengerLoadError(`Не удалось загрузить настройки: ${msg}`);
    } finally {
      setMessengerLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMessengerSettings();
  }, [loadMessengerSettings]);

  const setMaxField = (key, value) => {
    setMaxForm((f) => ({ ...f, [key]: value }));
  };

  const onMaxSubmit = async (e) => {
    e.preventDefault();
    setMaxSaving(true);
    setMaxStatusMsg("Сохранение…");
    setMaxStatusError(false);
    try {
      await api.put("/settings", { values: collectMaxPayload(maxForm) });
      setMaxStatusMsg("Сохранено.");
      setMaxStatusError(false);
      await loadMessengerSettings();
    } catch (err) {
      console.error(err);
      const body =
        typeof err?.response?.data === "string"
          ? err.response.data
          : err?.response?.data != null
            ? JSON.stringify(err.response.data)
            : err?.message ?? String(err);
      setMaxStatusMsg(`Ошибка: ${body}`);
      setMaxStatusError(true);
    } finally {
      setMaxSaving(false);
    }
  };

  const setTelegramField = (key, value) => {
    setTelegramForm((f) => ({ ...f, [key]: value }));
  };

  const onTelegramSubmit = async (e) => {
    e.preventDefault();
    const payload = collectTelegramPayload(telegramForm);
    if (Object.keys(payload).length === 0) {
      setTelegramStatusMsg("Введите новый токен или оставьте поле пустым (без изменений).");
      setTelegramStatusError(true);
      return;
    }
    setTelegramSaving(true);
    setTelegramStatusMsg("Сохранение…");
    setTelegramStatusError(false);
    try {
      await api.put("/settings", { values: payload });
      setTelegramStatusMsg("Сохранено.");
      setTelegramStatusError(false);
      await loadMessengerSettings();
    } catch (err) {
      console.error(err);
      const body =
        typeof err?.response?.data === "string"
          ? err.response.data
          : err?.response?.data != null
            ? JSON.stringify(err.response.data)
            : err?.message ?? String(err);
      setTelegramStatusMsg(`Ошибка: ${body}`);
      setTelegramStatusError(true);
    } finally {
      setTelegramSaving(false);
    }
  };

  const chatIntegrationIds = useMemo(
    () => rows.map((r) => String(r.id)).filter((id) => UUID_RE.test(id)),
    [rows],
  );

  const openCreate = () => {
    setEditingId(null);
    setEditSource(null);
    setEditFormLoading(false);
    setFormInitial(mapApiRowToForm({ name: "", base_url: "", auth: { auth_type: "NO_AUTH" }, actions: [] }));
    setBuilderErr("");
    setBuilderOpen(true);
  };

  const openEdit = async (id) => {
    setBuilderErr("");
    setEditingId(id);
    setEditSource(null);
    setFormInitial(null);
    setBuilderOpen(true);
    setEditFormLoading(true);
    try {
      const { data } = await api.get(`/v1/integrations/${id}`);
      setEditSource(data);
      setFormInitial(mapApiRowToForm(data));
    } catch (e) {
      console.error(e);
      setBuilderErr(formatApiDetail(e) || "Ошибка загрузки");
      setFormInitial(
        mapApiRowToForm({ name: "", base_url: "", auth: { auth_type: "NO_AUTH" }, actions: [] }),
      );
    } finally {
      setEditFormLoading(false);
    }
  };

  const closeBuilder = () => {
    setBuilderOpen(false);
    setEditingId(null);
    setEditSource(null);
    setFormInitial(null);
    setEditFormLoading(false);
    setBuilderErr("");
  };

  const onIntegrationFormSubmit = async (data) => {
    if (integrationSaving) return;
    setBuilderErr("");
    setIntegrationSaving(true);
    try {
      const payload = buildIntegrationCreatePayload(data);
      if (editSource && Array.isArray(editSource.webhooks) && editSource.webhooks.length > 0) {
        payload.webhooks = editSource.webhooks;
      }
      if (editingId) {
        await api.put(`/v1/integrations/${editingId}`, payload);
      } else {
        await api.post("/v1/integrations", payload);
      }
      closeBuilder();
      await loadList();
    } catch (e) {
      setBuilderErr(formatApiDetail(e) || "Ошибка сохранения");
    } finally {
      setIntegrationSaving(false);
    }
  };

  const onDeleteRow = async (id) => {
    if (!window.confirm("Удалить эту интеграцию?")) return;
    try {
      await api.delete(`/v1/integrations/${id}`);
      await loadList();
    } catch (e) {
      console.error(e);
      window.alert(formatApiDetail(e) || "Не удалось удалить");
    }
  };

  const modalRoot = typeof document !== "undefined" ? document.body : null;

  return (
    <div className={`w-full min-w-0 space-y-6 ${PAGE_TEXT}`}>
      <header className={PAGE_HEADER_BETWEEN}>
        <div className="flex items-center gap-3">
          <Plug className={PAGE_TITLE_ICON} strokeWidth={1.5} aria-hidden />
          <h1 className={PAGE_H1}>Интеграции</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={loadList}
            disabled={listLoading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-60"
          >
            <RefreshCcw className={`h-3.5 w-3.5 ${listLoading ? "animate-spin" : ""}`} aria-hidden />
            Обновить
          </button>
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden />
            Добавить
          </button>
        </div>
      </header>

      {listErr ? <p className="text-sm text-red-400">{listErr}</p> : null}

      <section className="rounded-2xl border border-slate-800 bg-slate-900/70">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-800 text-left text-sm text-slate-300">
            <thead className="bg-slate-900/60 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Название</th>
                <th className="px-4 py-3 font-medium min-w-[12rem]">Base URL</th>
                <th className="px-4 py-3 font-medium">Создана</th>
                <th className="px-4 py-3 font-medium">Обновлена</th>
                <th className="px-4 py-3 text-right font-medium">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {listLoading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                    Загрузка…
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                    Нет интеграций. Нажмите «Добавить» или откройте конструктор.
                  </td>
                </tr>
              ) : (
                rows.map((r) => {
                  const base = r.base_url != null ? String(r.base_url) : "";
                  return (
                    <tr key={r.id} className="border-b border-slate-800/80 hover:bg-slate-800/30">
                      <td className="px-4 py-3 font-medium text-slate-200">{r.name}</td>
                      <td className="px-4 py-3 max-w-[min(28rem,50vw)]">
                        <a
                          href={base}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex min-w-0 max-w-full items-center gap-1.5 break-all font-mono text-xs text-emerald-400 underline decoration-emerald-600/50 underline-offset-2 hover:text-emerald-300"
                          title={base}
                        >
                          <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden />
                          {base || "—"}
                        </a>
                      </td>
                      <td className="px-4 py-3 text-slate-400">{formatDateTimeRu(r.created_at)}</td>
                      <td className="px-4 py-3 text-slate-400">{formatDateTimeRu(r.updated_at)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex flex-wrap items-center justify-end gap-1">
                          <IconEditButton
                            title="Редактировать интеграцию"
                            onClick={() => openEdit(r.id)}
                          />
                          <IconDeleteButton
                            title="Удалить интеграцию"
                            onClick={() => onDeleteRow(r.id)}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {builderOpen && modalRoot
        ? createPortal(
            <div className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto bg-black/60 p-4">
              <div className="my-8 w-full max-w-[100rem] rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-white">
                    {editingId ? "Редактирование интеграции" : "Конструктор интеграции"}
                  </h2>
                  <button
                    type="button"
                    className="text-slate-400 hover:text-white"
                    onClick={closeBuilder}
                    aria-label="Закрыть"
                  >
                    ✕
                  </button>
                </div>
                {builderErr ? (
                  <p className="mb-4 rounded-lg border border-red-900/40 bg-red-950/20 px-3 py-2 text-sm text-red-200/95">
                    {builderErr}
                  </p>
                ) : null}
                {editFormLoading ? (
                  <p className="text-sm text-slate-400">Загрузка…</p>
                ) : formInitial ? (
                  <div className={integrationSaving ? "pointer-events-none opacity-60" : ""}>
                    <IntegrationForm
                      key={editingId || "new"}
                      showHeading={false}
                      initialData={formInitial}
                      onSubmit={onIntegrationFormSubmit}
                    />
                    {integrationSaving ? (
                      <p className="mt-2 text-sm text-slate-400">Сохранение…</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>,
            modalRoot,
          )
        : null}

      <section id="chats" className="space-y-4 scroll-mt-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-200">Чаты с агентом</h2>
          <p className="mt-1 text-sm text-slate-400">
            Потоковый ответ (SSE) с эндпоинта <code className="text-slate-300">POST /api/v1/chat/stream</code>. В запрос
            передаются идентификаторы интеграций из таблицы выше.
          </p>
          {chatIntegrationIds.length === 0 ? (
            <p className="mt-2 rounded-lg border border-amber-900/40 bg-amber-950/20 px-3 py-2 text-sm text-amber-100/90">
              Нет интеграций с UUID в списке — чат откроется без инструментов. Создайте интеграцию через «Добавить».
            </p>
          ) : null}
        </div>
        <AgentChat integrationIds={chatIntegrationIds} />
      </section>

      <section id="max" className="w-full min-w-0 space-y-4 scroll-mt-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-200">Мессенджер MAX</h2>
        </div>
        {messengerLoadError ? (
          <p className="rounded-lg border border-red-900/40 bg-red-950/20 px-3 py-2 text-sm text-red-200/95">
            {messengerLoadError}
          </p>
        ) : null}
        <p
          className={`min-h-[1.25rem] text-sm ${maxStatusError ? "text-red-400" : "text-emerald-400"}`}
          aria-live="polite"
        >
          {maxStatusMsg}
        </p>
        {messengerLoading ? (
          <p className="text-slate-400">Загрузка…</p>
        ) : (
          <form
            className="space-y-4 rounded-xl border border-slate-700/80 bg-slate-800/40 p-5 shadow-sm"
            onSubmit={onMaxSubmit}
          >
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-200" htmlFor="int-max-base-url">
                base_url
              </label>
              <p className="text-sm text-slate-400">
                Базовый URL HTTP API бота (отправка сообщений, вызовы и т.д.) — тот же, что использует сервер. Изменение
                только через переменные окружения <code className="text-slate-300">MAX_API_BASE</code> /{" "}
                <code className="text-slate-300">MAX_PLATFORM_API_BASE</code> (по умолчанию:{" "}
                <code className="text-slate-300">{MAX_INTEGRATION_BASE_URL}</code> и{" "}
                <code className="text-slate-300">{MAX_PLATFORM_API_BASE_DEFAULT}</code> для long poll).
              </p>
              <input
                id="int-max-base-url"
                className="w-full cursor-default rounded-lg border border-slate-600 bg-slate-950/80 px-3 py-2 text-sm text-slate-300"
                type="url"
                readOnly
                autoComplete="off"
                name="max_base_url"
                value={MAX_INTEGRATION_BASE_URL}
                title="MAX Bot API: значение по умолчанию сервера"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-200" htmlFor="int-max-bot-username">
                Ник бота MAX (<code className="text-xs">@id…_bot</code>)
              </label>
              <p className="text-sm text-slate-400">
                Подстрока в тексте (например <code className="text-xs">@id…_bot</code>). В групповых чатах бот
                обрабатывает сообщение только при наличии этого упоминания.
              </p>
              <input
                id="int-max-bot-username"
                className="w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                type="text"
                autoComplete="off"
                placeholder="@id6451417302_bot"
                value={maxForm.maxBotUsername}
                onChange={(e) => setMaxField("maxBotUsername", e.target.value)}
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-200" htmlFor="int-max-bot-token">
                Токен бота MAX
              </label>
              <p className="text-sm text-slate-400">{maxForm.maxBotHint}</p>
              <input
                id="int-max-bot-token"
                className="w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                type="password"
                autoComplete="off"
                placeholder="Оставьте пустым, чтобы не менять сохранённый токен"
                value={maxForm.maxBotToken}
                onChange={(e) => setMaxField("maxBotToken", e.target.value)}
              />
            </div>

            <div>
              <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-200">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-500 bg-slate-900 accent-emerald-500"
                  checked={maxForm.maxUsePolling}
                  onChange={(e) => setMaxField("maxUsePolling", e.target.checked)}
                />
                Использовать Long Polling (для локальной отладки)
              </label>
              <p className="mt-1.5 text-sm text-slate-400">
                Опрос <code className="text-xs">GET /updates</code> у MAX без публичного HTTPS. В продакшене выключайте и
                используйте Webhook.
              </p>
            </div>

            <div>
              <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-200">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-500 bg-slate-900 accent-emerald-500"
                  checked={maxForm.maxVoiceReply}
                  onChange={(e) => setMaxField("maxVoiceReply", e.target.checked)}
                />
                Озвучивать ответы в MAX
              </label>
              <p className="mt-1.5 text-sm text-slate-400">
                После текстового ответа отправляется голосовое вложение. Нужен настроенный TTS.
              </p>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-200" htmlFor="int-max-call-delay">
                Задержка ответа на входящий звонок MAX, сек
              </label>
              <p className="text-sm text-slate-400">
                Сколько секунд ждать перед отправкой команды «принять вызов» в API MAX.
              </p>
              <input
                id="int-max-call-delay"
                className="w-full max-w-xs rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                type="number"
                min={0}
                max={120}
                step={1}
                value={maxForm.maxCallAnswerDelay}
                onChange={(e) => setMaxField("maxCallAnswerDelay", e.target.value)}
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-200" htmlFor="int-max-greeting">
                Приветствие при ответе на звонок MAX
              </label>
              <textarea
                id="int-max-greeting"
                className="w-full resize-y rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                rows={2}
                placeholder={DEFAULT_MAX_GREETING}
                value={maxForm.maxCallGreeting}
                onChange={(e) => setMaxField("maxCallGreeting", e.target.value)}
              />
            </div>

            <button type="submit" className={BTN_SAVE} disabled={maxSaving}>
              <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
              Сохранить настройки MAX
            </button>
          </form>
        )}
      </section>

      <section id="telegram" className="w-full min-w-0 space-y-4 scroll-mt-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-200">Мессенджер Telegram</h2>
        </div>
        {messengerLoadError ? (
          <p className="rounded-lg border border-red-900/40 bg-red-950/20 px-3 py-2 text-sm text-red-200/95">
            {messengerLoadError}
          </p>
        ) : null}
        <p
          className={`min-h-[1.25rem] text-sm ${telegramStatusError ? "text-red-400" : "text-emerald-400"}`}
          aria-live="polite"
        >
          {telegramStatusMsg}
        </p>
        {messengerLoading ? (
          <p className="text-slate-400">Загрузка…</p>
        ) : (
          <form
            className="space-y-4 rounded-xl border border-slate-700/80 bg-slate-800/40 p-5 shadow-sm"
            onSubmit={onTelegramSubmit}
          >
            <div>
              <label
                className="mb-1 flex items-center gap-1 text-sm font-medium text-slate-200"
                htmlFor="int-telegram-token"
              >
                <span className="text-sky-400" aria-hidden>
                  ✈
                </span>
                Токен Telegram-бота
              </label>
              <p className="text-sm text-slate-400">{telegramForm.telegramHint}</p>
              <input
                id="int-telegram-token"
                className="w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                type="password"
                autoComplete="off"
                placeholder="Оставьте пустым, чтобы не менять сохранённый токен"
                value={telegramForm.telegramToken}
                onChange={(e) => setTelegramField("telegramToken", e.target.value)}
              />
            </div>
            <button type="submit" className={BTN_SAVE} disabled={telegramSaving}>
              <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
              Сохранить токен
            </button>
          </form>
        )}
      </section>

      <section id="vk" className="w-full min-w-0 space-y-4 scroll-mt-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-200">VK</h2>
          <p className="mt-1 text-sm text-slate-400">
            Настройки сообщества и Callback API для ВКонтакте — позже появятся здесь (аналогично MAX и Telegram).
          </p>
        </div>
        <div className="rounded-xl border border-slate-700/80 bg-slate-800/40 p-5 shadow-sm">
          <p className="m-0 text-sm text-slate-300">
            <span className="text-blue-400" aria-hidden>
              VK{" "}
            </span>
            Интеграция VK — <strong>в разработке</strong>. Вкладка зарезервирована под токены, подтверждение сервера и
            сценарии диалогов.
          </p>
        </div>
      </section>

      <section id="telephony" className="space-y-4 scroll-mt-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-200">Телефония</h2>
          <p className="mt-1 text-sm text-slate-400">Проверка голосового потока через WebSocket (раньше раздел «Тестер»).</p>
        </div>
        <VoiceTelephonyTestPanel />
      </section>
    </div>
  );
}
