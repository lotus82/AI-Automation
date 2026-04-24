import { useCallback, useEffect, useMemo, useState } from "react";
import { Plug, Save } from "lucide-react";
import { IconDeleteButton, IconEditButton } from "../components/ui/IconActionButtons.jsx";
import { useSearchParams } from "react-router-dom";
import api from "../api/client.js";
import { AgentChat } from "../components/Chat/AgentChat.jsx";
import { IntegrationForm } from "../components/integrations/IntegrationForm.jsx";
import { VoiceTelephonyTestPanel } from "../components/telephony/VoiceTelephonyTestPanel.jsx";
import { SK } from "../constants/systemSettingsKeys.js";
import { hintForSecretRow, mapFromList, parseTruthy } from "../utils/systemSettingsForm.js";
import {
  BTN_SAVE,
  BTN_SAVE_COMPACT,
  ICON_BTN,
  PAGE_H1,
  PAGE_HEADER,
  PAGE_TEXT,
  PAGE_TITLE_ICON,
} from "../styles/pageLayout.js";
import { formatDateTimeRu } from "../utils/dateTimeFormat.js";

const SYSTEM_OPTIONS = [{ value: "bitrix24", label: "Битрикс24" }];

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function newId() {
  return globalThis.crypto?.randomUUID?.() ?? `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** Демо-строка до появления API `/api/integrations`. */
function initialRows() {
  return [
    {
      id: "demo-bitrix24",
      name: "Битрикс24",
      systemKey: "bitrix24",
      createdAt: new Date("2024-06-01T09:00:00").toISOString(),
    },
  ];
}

const tabBtn = (active) =>
  `rounded-t-lg border px-4 py-2 text-sm font-medium transition-colors ${
    active
      ? "border-slate-600 border-b-transparent bg-slate-800/90 text-white"
      : "border-transparent text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
  }`;

const VALID_INTEGRATION_SECTIONS = new Set([
  "registry",
  "chats",
  "max",
  "telegram",
  "vk",
  "telephony",
  "builder",
]);

function readIntegrationSectionFromUrl() {
  try {
    const s = new URLSearchParams(window.location.search).get("section");
    return VALID_INTEGRATION_SECTIONS.has(s) ? s : "registry";
  } catch {
    return "registry";
  }
}

const DEFAULT_MAX_GREETING =
  "Здравствуйте! Это ИИ-помощник компании. Слушаю вас.";

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
    actions: data.actions.map((a) => ({
      ...a,
      parameters: (a.parameters || []).map((p) => ({
        ...p,
        type: mapParamTypeForApi(p.type),
      })),
    })),
  };
}

export function IntegrationsPage() {
  const [searchParams] = useSearchParams();
  const [section, setSection] = useState(readIntegrationSectionFromUrl);

  useEffect(() => {
    const s = searchParams.get("section");
    if (VALID_INTEGRATION_SECTIONS.has(s)) setSection(s);
  }, [searchParams]);
  const [rows, setRows] = useState(initialRows);
  const [builderStatus, setBuilderStatus] = useState(null);
  const [builderError, setBuilderError] = useState(null);
  const [name, setName] = useState("");
  const [systemKey, setSystemKey] = useState("bitrix24");
  const [formMsg, setFormMsg] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");

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

  const loadMessengerSettings = useCallback(async () => {
    setMessengerLoadError("");
    try {
      const { data: rows } = await api.get("/settings");
      const map = mapFromList(rows);
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

  const th =
    "px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400";
  const td = "px-3 py-2 align-middle text-sm text-slate-200";

  const onCreate = (e) => {
    e.preventDefault();
    const n = name.trim();
    if (!n) {
      setFormMsg("Укажите название интеграции.");
      return;
    }
    setRows((prev) => [
      {
        id: newId(),
        name: n,
        systemKey,
        createdAt: new Date().toISOString(),
      },
      ...prev,
    ]);
    setName("");
    setFormMsg("Интеграция добавлена в таблицу (локально, до подключения API).");
  };

  const startEdit = (row) => {
    setEditingId(row.id);
    setEditName(row.name);
  };

  const saveEdit = (id) => {
    const n = editName.trim();
    if (!n) return;
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, name: n } : r)));
    setEditingId(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  const onDelete = (id) => {
    if (!window.confirm("Удалить эту интеграцию из списка?")) return;
    setRows((prev) => prev.filter((r) => r.id !== id));
    if (editingId === id) setEditingId(null);
  };

  const tableMin = useMemo(() => "min-w-[640px]", []);

  const handleIntegrationFormSubmit = async (data) => {
    setBuilderStatus(null);
    setBuilderError(null);
    try {
      const res = await fetch("/api/v1/integrations", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(buildIntegrationCreatePayload(data)),
      });
      if (!res.ok) {
        const raw = await res.text();
        let msg = `Ошибка ${res.status}`;
        if (raw) {
          try {
            const j = JSON.parse(raw);
            if (j?.detail != null) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
            else msg = raw.slice(0, 800);
          } catch {
            msg = raw.slice(0, 800);
          }
        }
        setBuilderError(msg);
        return;
      }
      setBuilderStatus("Интеграция сохранена на сервере.");
    } catch (e) {
      setBuilderError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="w-full min-w-0 space-y-8 text-slate-100">
      <header className={PAGE_HEADER}>
        <Plug className={PAGE_TITLE_ICON} strokeWidth={1.5} aria-hidden />
        <h1 className={PAGE_H1}>Интеграции</h1>
      </header>

      <div className="flex flex-wrap gap-1 border-b border-slate-700/80">
        <button type="button" className={tabBtn(section === "registry")} onClick={() => setSection("registry")}>
          Реестр
        </button>
        <button type="button" className={tabBtn(section === "chats")} onClick={() => setSection("chats")}>
          Чаты
        </button>
        <button type="button" className={tabBtn(section === "max")} onClick={() => setSection("max")}>
          MAX
        </button>
        <button type="button" className={tabBtn(section === "telegram")} onClick={() => setSection("telegram")}>
          Telegram
        </button>
        <button type="button" className={tabBtn(section === "vk")} onClick={() => setSection("vk")}>
          VK
        </button>
        <button type="button" className={tabBtn(section === "telephony")} onClick={() => setSection("telephony")}>
          Телефония
        </button>
        <button type="button" className={tabBtn(section === "builder")} onClick={() => setSection("builder")}>
          Конструктор
        </button>
      </div>

      {section === "registry" ? (
        <>
          <section>
            <h2 className="mb-3 text-lg font-semibold text-slate-200">Новая интеграция</h2>
            <form
              className="w-full space-y-4 rounded-2xl border border-slate-700/80 bg-slate-900/50 p-5 shadow-lg backdrop-blur-sm"
              onSubmit={onCreate}
            >
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400" htmlFor="int-name">
                  Название
                </label>
                <input
                  id="int-name"
                  className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  placeholder="Например: CRM продаж"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400" htmlFor="int-system">
                  Внешняя система
                </label>
                <select
                  id="int-system"
                  className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  value={systemKey}
                  onChange={(e) => setSystemKey(e.target.value)}
                >
                  {SYSTEM_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="submit"
                className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-emerald-500"
              >
                Создать
              </button>
              {formMsg ? (
                <p className="text-sm text-slate-400" role="status">
                  {formMsg}
                </p>
              ) : null}
            </form>
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-slate-200">Список интеграций</h2>
            <div className={`overflow-x-auto rounded-xl border border-slate-700/80 bg-slate-900/40 ${tableMin}`}>
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-slate-600 bg-slate-900/60">
                    <th className={th}>Название</th>
                    <th className={th}>Дата создания</th>
                    <th className={`${th} w-[1%] whitespace-nowrap`}>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="px-3 py-8 text-center text-slate-500">
                        Нет интеграций. Создайте первую через форму выше.
                      </td>
                    </tr>
                  ) : (
                    rows.map((row) => (
                      <tr key={row.id} className="border-b border-slate-700/80 hover:bg-slate-800/40">
                        <td className={td}>
                          {editingId === row.id ? (
                            <input
                              className="w-full min-w-[8rem] rounded border border-slate-600 bg-slate-950 px-2 py-1 text-sm"
                              value={editName}
                              onChange={(e) => setEditName(e.target.value)}
                              aria-label="Редактировать название"
                            />
                          ) : (
                            <span className="font-medium text-white">{row.name}</span>
                          )}
                        </td>
                        <td className={`${td} whitespace-nowrap text-slate-400`}>
                          {formatDateTimeRu(row.createdAt)}
                        </td>
                        <td className={`${td} whitespace-nowrap`}>
                          {editingId === row.id ? (
                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                className={`${BTN_SAVE_COMPACT} text-xs`}
                                onClick={() => saveEdit(row.id)}
                              >
                                <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
                                Сохранить
                              </button>
                              <button
                                type="button"
                                className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
                                onClick={cancelEdit}
                              >
                                Отмена
                              </button>
                            </div>
                          ) : (
                            <div className="flex flex-wrap items-center gap-1">
                              <IconEditButton title="Редактировать название" onClick={() => startEdit(row)} />
                              <IconDeleteButton title="Удалить интеграцию" onClick={() => onDelete(row.id)} />
                            </div>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : section === "chats" ? (
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-200">Чаты с агентом</h2>
            <p className="mt-1 text-sm text-slate-400">
              Потоковый ответ (SSE) с эндпоинта <code className="text-slate-300">POST /api/v1/chat/stream</code>. В
              запрос передаются интеграции с валидным UUID из реестра (после синхронизации с API).
            </p>
            {chatIntegrationIds.length === 0 ? (
              <p className="mt-2 rounded-lg border border-amber-900/40 bg-amber-950/20 px-3 py-2 text-sm text-amber-100/90">
                Сейчас в таблице нет строк с UUID интеграции — чат откроется без инструментов. Добавьте записи из
                бэкенда или вставьте UUID в данные реестра.
              </p>
            ) : null}
          </div>
          <AgentChat integrationIds={chatIntegrationIds} />
        </section>
      ) : section === "max" ? (
        <section className="w-full min-w-0 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-200">Мессенджер MAX</h2>
          </div>
          {messengerLoadError ? (
            <p className="rounded-lg border border-red-900/40 bg-red-950/20 px-3 py-2 text-sm text-red-200/95">{messengerLoadError}</p>
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
      ) : section === "telegram" ? (
        <section className="w-full min-w-0 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-200">Мессенджер Telegram</h2>
          </div>
          {messengerLoadError ? (
            <p className="rounded-lg border border-red-900/40 bg-red-950/20 px-3 py-2 text-sm text-red-200/95">{messengerLoadError}</p>
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
                <label className="mb-1 flex items-center gap-1 text-sm font-medium text-slate-200" htmlFor="int-telegram-token">
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
      ) : section === "vk" ? (
        <section className="w-full min-w-0 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-200">VK</h2>
            <p className="mt-1 text-sm text-slate-400">
              Настройки сообщества и Callback API для ВКонтакте — позже появятся здесь (аналогично вкладкам MAX и
              Telegram).
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
      ) : section === "telephony" ? (
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-200">Телефония</h2>
            <p className="mt-1 text-sm text-slate-400">
              Проверка голосового потока через WebSocket — ранее раздел «Тестирование».
            </p>
          </div>
          <VoiceTelephonyTestPanel />
        </section>
      ) : section === "builder" ? (
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-200">Конструктор интеграции</h2>
            <p className="mt-1 text-sm text-slate-400">
              Полная конфигурация для <code className="text-slate-300">POST /api/v1/integrations</code> (поля{" "}
              <code className="text-slate-300">webhooks</code> добавляются автоматически, тип{" "}
              <code className="text-slate-300">integer</code> параметра маппится в <code className="text-slate-300">number</code>).
            </p>
          </div>
          {builderStatus ? (
            <p className="rounded-lg border border-emerald-900/40 bg-emerald-950/20 px-3 py-2 text-sm text-emerald-100/95">
              {builderStatus}
            </p>
          ) : null}
          {builderError ? (
            <p className="rounded-lg border border-red-900/40 bg-red-950/20 px-3 py-2 text-sm text-red-200/95 whitespace-pre-wrap">
              {builderError}
            </p>
          ) : null}
          <IntegrationForm onSubmit={handleIntegrationFormSubmit} />
        </section>
      ) : null}
    </div>
  );
}
