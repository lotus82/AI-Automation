import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { Plug, Plus, RefreshCcw } from "lucide-react";
import { IconEditButton } from "../components/ui/IconActionButtons.jsx";
import api from "../api/client.js";
import { IntegrationForm } from "../components/integrations/IntegrationForm.jsx";
import { IntegrationsSystemModalBody } from "./IntegrationsSystemModalBody.jsx";
import { SK } from "../constants/systemSettingsKeys.js";
import { hintForSecretRow, mapFromList, parseTruthy } from "../utils/systemSettingsForm.js";
import { PAGE_H1, PAGE_HEADER_BETWEEN, PAGE_TEXT, PAGE_TITLE_ICON } from "../styles/pageLayout.js";
import { formatDateTimeRu } from "../utils/dateTimeFormat.js";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const DEFAULT_MAX_GREETING =
  "Здравствуйте! Это ИИ-помощник компании. Слушаю вас.";

const FERNET_KEY_GENERATE_CMD =
  'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"';

function isIntegrationFernetKeyError(message) {
  return typeof message === "string" && message.includes("INTEGRATION_FERNET_KEY");
}

/** Подсистемы панели: в таблице вместе с API-интеграциями; anchor — ключ модального окна и hash. */
const BUILTIN_INTEGRATION_ROWS = [
  { key: "sys-chats", name: "Чаты с агентом", anchor: "chats" },
  { key: "sys-max", name: "Мессенджер MAX", anchor: "max" },
  { key: "sys-telegram", name: "Мессенджер Telegram", anchor: "telegram" },
  { key: "sys-vk", name: "VK", anchor: "vk" },
  { key: "sys-telephony", name: "Телефония", anchor: "telephony" },
];
const VALID_SYSTEM_INTEGRATION_ANCHORS = new Set(BUILTIN_INTEGRATION_ROWS.map((r) => r.anchor));
function titleForSystemModal(anchor) {
  return BUILTIN_INTEGRATION_ROWS.find((r) => r.anchor === anchor)?.name ?? "Интеграция";
}

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

function IntegrationReadonlySummary({ data }) {
  if (!data) return null;
  const base = data.base_url != null ? String(data.base_url) : "—";
  const authType =
    data.auth && typeof data.auth === "object" && data.auth.auth_type != null
      ? String(data.auth.auth_type)
      : "—";
  const nAct = Array.isArray(data.actions) ? data.actions.length : 0;
  const nWh = Array.isArray(data.webhooks) ? data.webhooks.length : 0;
  return (
    <div className="mb-6 space-y-3 rounded-xl border border-slate-700/90 bg-slate-950/40 p-4 text-sm text-slate-200">
      <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">Содержимое интеграции</h3>
      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <dt className="text-xs text-slate-500">ID</dt>
          <dd className="mt-0.5 break-all font-mono text-xs text-slate-200">{String(data.id)}</dd>
        </div>
        <div className="sm:col-span-1 lg:col-span-2">
          <dt className="text-xs text-slate-500">Base URL</dt>
          <dd className="mt-0.5 break-all font-mono text-xs text-slate-200" title={base}>
            {base}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Авторизация</dt>
          <dd className="mt-0.5 text-slate-200">{authType}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Действия / вебхуки</dt>
          <dd className="mt-0.5 text-slate-200">
            {nAct} / {nWh}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Создана</dt>
          <dd className="mt-0.5 text-slate-300">{formatDateTimeRu(data.created_at)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Обновлена</dt>
          <dd className="mt-0.5 text-slate-300">{formatDateTimeRu(data.updated_at)}</dd>
        </div>
      </dl>
    </div>
  );
}

export function IntegrationsPage() {
  const location = useLocation();
  const navigate = useNavigate();

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
  const [systemModal, setSystemModal] = useState(null);

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

  const closeSystemModal = useCallback(() => {
    setSystemModal(null);
    navigate(
      { pathname: location.pathname, search: location.search, hash: "" },
      { replace: true },
    );
  }, [navigate, location.pathname, location.search]);

  const openSystemIntegrationModal = useCallback(
    (anchor) => {
      if (!VALID_SYSTEM_INTEGRATION_ANCHORS.has(anchor)) return;
      setBuilderOpen(false);
      setSystemModal(anchor);
    },
    [],
  );

  useEffect(() => {
    const h = (location.hash || "").replace(/^#/, "");
    if (h && VALID_SYSTEM_INTEGRATION_ANCHORS.has(h)) {
      setBuilderOpen(false);
      setSystemModal(h);
    }
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
    setSystemModal(null);
    setEditingId(null);
    setEditSource(null);
    setEditFormLoading(false);
    setFormInitial(mapApiRowToForm({ name: "", base_url: "", auth: { auth_type: "NO_AUTH" }, actions: [] }));
    setBuilderErr("");
    setBuilderOpen(true);
  };

  const openEdit = async (id) => {
    setSystemModal(null);
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

      {listErr ? (
        isIntegrationFernetKeyError(listErr) ? (
          <div
            className="rounded-2xl border border-amber-800/50 bg-amber-950/25 px-4 py-3 text-sm text-amber-100/95"
            role="alert"
          >
            <p className="m-0 font-medium text-amber-50">{listErr}</p>
            <p className="mt-2 text-amber-100/85">
              Без ключа нельзя хранить секреты интеграций в БД. На сервере (или в{" "}
              <code className="text-xs text-amber-200/95">.env</code> рядом с{" "}
              <code className="text-xs text-amber-200/95">docker-compose</code>) задайте переменную и перезапустите
              контейнер API:
            </p>
            <ol className="mt-2 list-decimal space-y-2 pl-5 text-amber-100/90">
              <li>
                Сгенерируйте ключ (одна строка, 44 символа):
                <pre className="mt-1 overflow-x-auto rounded-lg border border-amber-900/50 bg-slate-950/80 p-2 font-mono text-xs text-amber-100/90">
                  {FERNET_KEY_GENERATE_CMD}
                </pre>
              </li>
              <li>
                В <code className="text-xs">.env</code> добавьте, например:{" "}
                <code className="whitespace-pre-wrap break-all text-xs text-amber-200/95">
                  INTEGRATION_FERNET_KEY=ваш_сгенерированный_ключ
                </code>
              </li>
              <li>
                <code className="text-xs">docker compose -f docker-compose.prod.yml up -d</code> (или ваш способ) —
                чтобы сервис перечитал окружение.
              </li>
            </ol>
            <p className="mt-2 text-xs text-amber-200/70">
              Тот же ключ должен оставаться неизменным, иначе уже сохранённые в БД секреты интеграций не расшифруются.
            </p>
          </div>
        ) : (
          <p className="text-sm text-red-400">{listErr}</p>
        )
      ) : null}

      <section className="rounded-2xl border border-slate-800 bg-slate-900/70">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-800 text-left text-sm text-slate-300">
            <thead className="bg-slate-900/60 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Название</th>
                <th className="w-[1%] px-4 py-3 text-right font-medium" scope="col">
                  <span className="sr-only">Редактировать</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {BUILTIN_INTEGRATION_ROWS.map((row) => (
                <tr
                  key={row.key}
                  className="border-b border-slate-800/80 bg-slate-900/20 hover:bg-slate-800/30"
                >
                  <td className="px-4 py-3 font-medium text-slate-200">{row.name}</td>
                  <td className="px-4 py-3 text-right">
                    <IconEditButton
                      title="Редактировать"
                      aria-label={`Редактировать: ${row.name}`}
                      onClick={() => openSystemIntegrationModal(row.anchor)}
                    />
                  </td>
                </tr>
              ))}
              {listLoading ? (
                <tr>
                  <td colSpan={2} className="px-4 py-4 text-center text-slate-500">
                    Загрузка API-интеграций…
                  </td>
                </tr>
              ) : listErr ? (
                <tr>
                  <td colSpan={2} className="px-4 py-3 text-center text-sm text-amber-200/90">
                    Список API-интеграций с сервера не загружен (см. сообщение выше).
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={2} className="px-4 py-4 text-center text-slate-500">
                    В реестре API пока нет интеграций — нажмите «Добавить».
                  </td>
                </tr>
              ) : (
                <>
                  <tr className="border-b border-slate-800/60 bg-slate-900/50">
                    <td colSpan={2} className="px-4 py-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                      API-интеграции
                    </td>
                  </tr>
                  {rows.map((r) => (
                    <tr key={r.id} className="border-b border-slate-800/80 hover:bg-slate-800/30">
                      <td className="px-4 py-3 font-medium text-slate-200">{r.name}</td>
                      <td className="px-4 py-3 text-right">
                        <IconEditButton
                          title="Редактировать"
                          aria-label="Редактировать"
                          onClick={() => openEdit(r.id)}
                        />
                      </td>
                    </tr>
                  ))}
                </>
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
                    {editingId ? "Интеграция" : "Конструктор интеграции"}
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
                  isIntegrationFernetKeyError(builderErr) ? (
                    <div
                      className="mb-4 rounded-lg border border-amber-800/50 bg-amber-950/25 px-3 py-2 text-sm text-amber-100/95"
                      role="alert"
                    >
                      <p className="m-0 font-medium text-amber-50">{builderErr}</p>
                      <p className="mt-1 text-xs text-amber-100/85">
                        См. шаги на странице (блок с командой <code>python -c &quot;…Fernet…&quot;</code>) или в{" "}
                        <code className="text-amber-200/90">.env.example</code>.
                      </p>
                    </div>
                  ) : (
                    <p className="mb-4 rounded-lg border border-red-900/40 bg-red-950/20 px-3 py-2 text-sm text-red-200/95">
                      {builderErr}
                    </p>
                  )
                ) : null}
                {editFormLoading ? (
                  <p className="text-sm text-slate-400">Загрузка…</p>
                ) : formInitial ? (
                  <div className={integrationSaving ? "pointer-events-none opacity-60" : ""}>
                    {editingId && editSource ? <IntegrationReadonlySummary data={editSource} /> : null}
                    {editingId ? (
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Конфигурация</p>
                    ) : null}
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

      {systemModal && modalRoot
        ? createPortal(
            <div
              className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto bg-black/60 p-4"
              onClick={(e) => e.target === e.currentTarget && closeSystemModal()}
              role="presentation"
            >
              <div
                className="my-4 flex max-h-[min(95vh,56rem)] w-full max-w-[100rem] flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900 shadow-xl"
                onClick={(e) => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-labelledby="integration-system-modal-title"
              >
                <div className="flex shrink-0 items-center justify-between border-b border-slate-800 px-5 py-3">
                  <h2 id="integration-system-modal-title" className="text-lg font-semibold text-white">
                    {titleForSystemModal(systemModal)}
                  </h2>
                  <button
                    type="button"
                    className="text-slate-400 hover:text-white"
                    onClick={closeSystemModal}
                    aria-label="Закрыть"
                  >
                    ✕
                  </button>
                </div>
                <div className="min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden px-5 py-4">
                  <IntegrationsSystemModalBody
                    systemModal={systemModal}
                    chatIntegrationIds={chatIntegrationIds}
                    messengerLoadError={messengerLoadError}
                    messengerLoading={messengerLoading}
                    maxForm={maxForm}
                    setMaxField={setMaxField}
                    onMaxSubmit={onMaxSubmit}
                    maxSaving={maxSaving}
                    maxStatusMsg={maxStatusMsg}
                    maxStatusError={maxStatusError}
                    telegramForm={telegramForm}
                    setTelegramField={setTelegramField}
                    onTelegramSubmit={onTelegramSubmit}
                    telegramSaving={telegramSaving}
                    telegramStatusMsg={telegramStatusMsg}
                    telegramStatusError={telegramStatusError}
                  />
                </div>
              </div>
            </div>,
            modalRoot,
          )
        : null}

    </div>
  );
}
