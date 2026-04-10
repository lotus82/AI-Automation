import { useMemo, useState } from "react";
import { AgentChat } from "../components/Chat/AgentChat.jsx";
import { IntegrationForm } from "../components/integrations/IntegrationForm.jsx";

const SYSTEM_OPTIONS = [{ value: "bitrix24", label: "Битрикс24" }];

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function formatRuDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

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
  const [section, setSection] = useState("registry");
  const [rows, setRows] = useState(initialRows);
  const [builderStatus, setBuilderStatus] = useState(null);
  const [builderError, setBuilderError] = useState(null);
  const [name, setName] = useState("");
  const [systemKey, setSystemKey] = useState("bitrix24");
  const [formMsg, setFormMsg] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");

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
    <div className="mx-auto max-w-5xl space-y-8 text-slate-100">
      <div>
        <h1 className="text-2xl font-bold text-white">Интеграции</h1>
        <p className="mt-2 text-sm text-slate-400">
          Подключения к внешним системам (REST, вебхуки). Список ниже можно позже связать с бэкендом модуля
          Universal API Integration.
        </p>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-slate-700/80">
        <button type="button" className={tabBtn(section === "registry")} onClick={() => setSection("registry")}>
          Реестр
        </button>
        <button type="button" className={tabBtn(section === "chats")} onClick={() => setSection("chats")}>
          Чаты
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
              className="max-w-xl space-y-4 rounded-2xl border border-slate-700/80 bg-slate-900/50 p-5 shadow-lg backdrop-blur-sm"
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
                          {formatRuDate(row.createdAt)}
                        </td>
                        <td className={`${td} whitespace-nowrap`}>
                          {editingId === row.id ? (
                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                className="rounded bg-emerald-700 px-2 py-1 text-xs text-white hover:bg-emerald-600"
                                onClick={() => saveEdit(row.id)}
                              >
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
                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                className="rounded border border-slate-600 px-2 py-1 text-xs text-sky-300 hover:bg-slate-800"
                                onClick={() => startEdit(row)}
                              >
                                Редактировать
                              </button>
                              <button
                                type="button"
                                className="rounded border border-red-900/50 px-2 py-1 text-xs text-red-300 hover:bg-red-950/30"
                                onClick={() => onDelete(row.id)}
                              >
                                Удалить
                              </button>
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
      ) : (
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
      )}
    </div>
  );
}
