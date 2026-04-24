import { Save } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import api from "../api/client.js";
import { IconDeleteButton, IconEditButton } from "../components/ui/IconActionButtons.jsx";
import { BTN_SAVE, ICON_BTN } from "../styles/pageLayout.js";
import { formatDateTimeRu } from "../utils/dateTimeFormat.js";

function formatDetail(detail) {
  if (detail == null) return "";
  if (typeof detail === "string") return detail;
  return JSON.stringify(detail);
}

function formatApiError(err) {
  const d = err?.response?.data?.detail;
  if (d !== undefined) return formatDetail(d);
  return err?.message ?? String(err);
}

function buildCreateBody(form) {
  const t = form.type;
  const body = {
    chat_id: form.chatId.trim(),
    is_active: form.active,
    type: t,
    prompt: form.prompt,
    content_template: form.content,
    interval_settings: {},
    reminder_offset_minutes: null,
  };
  if (t === "INTERVAL") {
    body.interval_settings = {
      days: parseInt(form.days || "0", 10) || 0,
      hours: parseInt(form.hours || "0", 10) || 0,
      minutes: parseInt(form.minutes || "0", 10) || 0,
    };
  }
  if (t === "REMINDER") {
    body.reminder_offset_minutes = parseInt(form.offset || "0", 10) || 0;
  }
  return body;
}

function buildPatchBody(edit) {
  const t = edit.type;
  const body = {
    chat_id: edit.chatId.trim(),
    is_active: edit.active,
    type: t,
    prompt: edit.prompt,
    content_template: edit.content,
    interval_settings: {},
    reminder_offset_minutes: null,
  };
  if (t === "INTERVAL") {
    body.interval_settings = {
      days: parseInt(edit.days || "0", 10) || 0,
      hours: parseInt(edit.hours || "0", 10) || 0,
      minutes: parseInt(edit.minutes || "0", 10) || 0,
    };
  }
  if (t === "REMINDER") {
    body.reminder_offset_minutes = parseInt(edit.offset || "0", 10) || 0;
  }
  return body;
}

const initialCreate = {
  chatId: "",
  type: "DATABASE",
  active: true,
  days: "0",
  hours: "0",
  minutes: "60",
  offset: "60",
  prompt: "",
  content: "",
};

const emptyEdit = {
  id: null,
  chatId: "",
  type: "DATABASE",
  active: false,
  days: "0",
  hours: "0",
  minutes: "0",
  offset: "0",
  prompt: "",
  content: "",
};

function rowToEditState(r) {
  const intv = r.interval_settings || {};
  return {
    id: String(r.id),
    chatId: r.chat_id || "",
    type: r.type || "DATABASE",
    active: !!r.is_active,
    days: intv.days != null ? String(intv.days) : "0",
    hours: intv.hours != null ? String(intv.hours) : "0",
    minutes: intv.minutes != null ? String(intv.minutes) : "0",
    offset:
      r.reminder_offset_minutes != null
        ? String(r.reminder_offset_minutes)
        : "0",
    prompt: r.prompt != null ? r.prompt : "",
    content: r.content_template != null ? r.content_template : "",
  };
}

export function SchedulePage() {
  const [rows, setRows] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(false);

  const [create, setCreate] = useState(initialCreate);
  const [createMsg, setCreateMsg] = useState("");
  const [createMsgKind, setCreateMsgKind] = useState(null);
  const [creating, setCreating] = useState(false);

  const [editOpen, setEditOpen] = useState(false);
  const [edit, setEdit] = useState(emptyEdit);
  const [editMsg, setEditMsg] = useState("");
  const [editMsgKind, setEditMsgKind] = useState(null);
  const [savingEdit, setSavingEdit] = useState(false);

  const [toggleBusyId, setToggleBusyId] = useState(null);
  const uploadInputRef = useRef(null);
  const [uploadTargetId, setUploadTargetId] = useState(null);

  const loadList = useCallback(async () => {
    setListLoading(true);
    setListError(false);
    try {
      const { data } = await api.get("/schedules");
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error(e);
      setRows([]);
      setListError(true);
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    if (!editOpen) return;
    const onKey = (e) => {
      if (e.key === "Escape") setEditOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editOpen]);

  const setCreateField = (key, value) => {
    setCreate((c) => ({ ...c, [key]: value }));
  };

  const showInterval = create.type === "INTERVAL";
  const showReminder = create.type === "REMINDER";
  const showDbHintCreate = create.type === "DATABASE";

  const showIntervalEdit = edit.type === "INTERVAL";
  const showReminderEdit = edit.type === "REMINDER";
  const showDbHintEdit = edit.type === "DATABASE";

  const onCreateSubmit = async (ev) => {
    ev.preventDefault();
    setCreating(true);
    setCreateMsg("Сохранение…");
    setCreateMsgKind(null);
    try {
      await api.post("/schedules", buildCreateBody(create));
      setCreateMsg("Расписание создано.");
      setCreateMsgKind("ok");
      setCreate({ ...initialCreate });
      await loadList();
    } catch (e) {
      console.error(e);
      setCreateMsg(formatApiError(e));
      setCreateMsgKind("err");
    } finally {
      setCreating(false);
    }
  };

  const openEditModal = (r) => {
    setEdit(rowToEditState(r));
    setEditMsg("");
    setEditMsgKind(null);
    setEditOpen(true);
  };

  const closeEditModal = () => {
    setEditOpen(false);
  };

  const setEditField = (key, value) => {
    setEdit((x) => ({ ...x, [key]: value }));
  };

  const onEditSubmit = async (ev) => {
    ev.preventDefault();
    if (!edit.id) return;
    setSavingEdit(true);
    setEditMsg("Сохранение…");
    setEditMsgKind(null);
    try {
      await api.patch(`/schedules/${encodeURIComponent(edit.id)}`, buildPatchBody(edit));
      closeEditModal();
      await loadList();
    } catch (e) {
      console.error(e);
      setEditMsg(formatApiError(e));
      setEditMsgKind("err");
    } finally {
      setSavingEdit(false);
    }
  };

  const onToggleActive = async (id, nextActive) => {
    setToggleBusyId(id);
    try {
      await api.patch(`/schedules/${encodeURIComponent(id)}`, {
        is_active: nextActive,
      });
      await loadList();
    } catch (e) {
      window.alert(`Ошибка: ${formatApiError(e)}`);
    } finally {
      setToggleBusyId(null);
    }
  };

  const onDelete = async (id) => {
    if (!window.confirm("Удалить это расписание и все события?")) return;
    try {
      await api.delete(`/schedules/${encodeURIComponent(id)}`);
      await loadList();
    } catch (e) {
      window.alert(`Ошибка удаления: ${formatApiError(e)}`);
    }
  };

  const triggerUpload = (id) => {
    setUploadTargetId(id);
    uploadInputRef.current?.click();
  };

  const onUploadChange = async (ev) => {
    const input = ev.target;
    const file = input.files?.[0];
    const sid = uploadTargetId;
    setUploadTargetId(null);
    input.value = "";
    if (!file || !sid) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post(
        `/schedules/${encodeURIComponent(sid)}/upload-events`,
        fd
      );
      const n = data?.imported != null ? data.imported : 0;
      window.alert(`Импортировано событий: ${n}`);
    } catch (e) {
      window.alert(`Ошибка загрузки: ${formatApiError(e)}`);
    }
  };

  const inputClass =
    "w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500";
  const labelClass = "mb-1 block text-sm font-medium text-slate-200";
  const helpClass = "mt-0 text-sm text-slate-400";
  const panelClass =
    "mb-8 rounded-xl border border-slate-700/80 bg-slate-800/40 p-5 shadow-sm";
  const btnPrimary = BTN_SAVE;
  const btnSecondary =
    "inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-50";

  const createMsgClass =
    createMsgKind === "err"
      ? "text-red-400"
      : createMsgKind === "ok"
        ? "text-emerald-400"
        : "text-slate-400";

  const editMsgClass =
    editMsgKind === "err"
      ? "text-red-400"
      : editMsgKind === "ok"
        ? "text-emerald-400"
        : "text-slate-400";

  return (
    <div className={`w-full min-w-0 space-y-6 ${PAGE_TEXT}`}>
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/20 text-amber-300">
            <span aria-hidden>📅</span>
          </div>
          <h1 className={PAGE_H1}>Расписания</h1>
        </div>
      </header>
      
      <section className={panelClass} aria-labelledby="sch-new-title">
        <h2 id="sch-new-title" className="mb-4 text-lg font-semibold text-slate-100">
          ➕ Новое расписание
        </h2>
        <form className="space-y-4" onSubmit={onCreateSubmit}>
          <div>
            <label className={labelClass} htmlFor="sch-chat-id">
              chat_id (MAX)
            </label>
            <input
              id="sch-chat-id"
              type="text"
              className={inputClass}
              required
              placeholder="Например 123456789"
              value={create.chatId}
              onChange={(e) => setCreateField("chatId", e.target.value)}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="sch-type">
              Тип триггера
            </label>
            <select
              id="sch-type"
              className={inputClass}
              value={create.type}
              onChange={(e) => setCreateField("type", e.target.value)}
            >
              <option value="DATABASE">
                DATABASE — по дате события (календарь / ежегодно)
              </option>
              <option value="INTERVAL">INTERVAL — повтор с интервалом</option>
              <option value="REMINDER">
                REMINDER — напоминание до event_datetime
              </option>
            </select>
          </div>
          <div>
            <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-200">
              <input
                type="checkbox"
                id="sch-active"
                className="h-4 w-4 rounded border-slate-500 bg-slate-900 accent-sky-500"
                checked={create.active}
                onChange={(e) => setCreateField("active", e.target.checked)}
              />
              Активно
            </label>
          </div>

          {showInterval && (
            <div
              className="flex flex-wrap gap-3 rounded-lg border border-slate-700/60 bg-slate-900/30 p-3"
              id="sch-interval-block"
            >
              <p className={`${helpClass} mb-1 w-full`}>
                Интервал отсчитывается от реального времени; тик планировщика
                привязан к часовому поясу{" "}
                <strong>Саратов (UTC+4)</strong>.
              </p>
              <div className="min-w-[6rem] flex-1">
                <label className={labelClass} htmlFor="sch-days">
                  Дни
                </label>
                <input
                  id="sch-days"
                  type="number"
                  min={0}
                  className={inputClass}
                  value={create.days}
                  onChange={(e) => setCreateField("days", e.target.value)}
                />
              </div>
              <div className="min-w-[6rem] flex-1">
                <label className={labelClass} htmlFor="sch-hours">
                  Часы
                </label>
                <input
                  id="sch-hours"
                  type="number"
                  min={0}
                  className={inputClass}
                  value={create.hours}
                  onChange={(e) => setCreateField("hours", e.target.value)}
                />
              </div>
              <div className="min-w-[6rem] flex-1">
                <label className={labelClass} htmlFor="sch-minutes">
                  Минуты
                </label>
                <input
                  id="sch-minutes"
                  type="number"
                  min={0}
                  className={inputClass}
                  value={create.minutes}
                  onChange={(e) => setCreateField("minutes", e.target.value)}
                />
              </div>
            </div>
          )}

          {showReminder && (
            <div id="sch-reminder-block">
              <label className={labelClass} htmlFor="sch-offset">
                За сколько минут до события напомнить
              </label>
              <input
                id="sch-offset"
                type="number"
                min={0}
                className={inputClass}
                value={create.offset}
                onChange={(e) => setCreateField("offset", e.target.value)}
              />
              <span className={`${helpClass} mt-1.5 block`}>
                Момент события в файле — по{" "}
                <strong>Саратову (UTC+4)</strong>, если в дате нет часового
                пояса.
              </span>
            </div>
          )}

          {showDbHintCreate && (
            <p id="sch-db-hint" className={helpClass}>
              Для ежегодных дат в JSON события укажите{" "}
              <code className="text-xs">annual: true</code> (или{" "}
              <code className="text-xs">ezhegodno: true</code>). Даты в CSV/JSON
              без смещения считаются <strong>саратовским временем</strong>.
            </p>
          )}

          <div>
            <label className={labelClass} htmlFor="sch-prompt">
              Доп. инструкции для LLM
            </label>
            <textarea
              id="sch-prompt"
              className={`${inputClass} resize-y`}
              rows={3}
              placeholder="Как сформулировать сообщение, тон, ограничения"
              value={create.prompt}
              onChange={(e) => setCreateField("prompt", e.target.value)}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="sch-content">
              Шаблон / описание события
            </label>
            <textarea
              id="sch-content"
              className={`${inputClass} resize-y`}
              rows={3}
              placeholder="Базовый текст задачи для модели (контекст рассылки)"
              value={create.content}
              onChange={(e) => setCreateField("content", e.target.value)}
            />
          </div>
          <div>
            <button type="submit" className={btnSecondary} disabled={creating}>
              Создать
            </button>
          </div>
        </form>
        <p
          id="sch-form-msg"
          className={`mt-3 min-h-[1.25rem] text-sm ${createMsgClass}`}
          aria-live="polite"
        >
          {createMsg}
        </p>
      </section>

      <h2 className="mb-3 text-lg font-semibold text-slate-100">
        📋 Существующие расписания
      </h2>
      <div className="overflow-x-auto rounded-xl border border-slate-700/80 bg-slate-800/40">
        <table className="w-full min-w-[720px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-slate-600 bg-slate-900/50 text-xs uppercase tracking-wide text-slate-400">
              <th className="px-3 py-2 font-medium">ID</th>
              <th className="px-3 py-2 font-medium">chat_id</th>
              <th className="px-3 py-2 font-medium">Тип</th>
              <th className="px-3 py-2 font-medium">Активно</th>
              <th className="px-3 py-2 font-medium">Последний запуск</th>
              <th className="px-3 py-2 font-medium">Запуск / пауза</th>
              <th className="px-3 py-2 w-12 font-medium">
                <span className="sr-only">Редактировать</span>
              </th>
              <th className="px-3 py-2 font-medium">Данные</th>
              <th className="px-3 py-2 w-12 font-medium">
                <span className="sr-only">Удалить</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {listLoading ? (
              <tr>
                <td
                  colSpan={9}
                  className="px-3 py-6 text-center text-slate-500"
                >
                  Загрузка…
                </td>
              </tr>
            ) : listError ? (
              <tr>
                <td
                  colSpan={9}
                  className="px-3 py-6 text-center text-slate-500"
                >
                  Не удалось загрузить список.
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td
                  colSpan={9}
                  className="px-3 py-6 text-center text-slate-500"
                >
                  Нет расписаний. Создайте выше.
                </td>
              </tr>
            ) : (
              rows.map((r) => {
                const id = String(r.id);
                const nextActive = !r.is_active;
                return (
                  <tr
                    key={id}
                    className="border-b border-slate-700/80 hover:bg-slate-800/60"
                  >
                    <td className="px-3 py-2 align-top font-mono text-xs text-sky-300">
                      {id}
                    </td>
                    <td className="px-3 py-2 align-top">{r.chat_id}</td>
                    <td className="px-3 py-2 align-top">{r.type}</td>
                    <td className="px-3 py-2 align-top">
                      {r.is_active ? "да" : "нет"}
                    </td>
                    <td className="px-3 py-2 align-top text-slate-300">
                      {formatDateTimeRu(r.last_run_at)}
                    </td>
                    <td className="px-3 py-2 align-top">
                      <button
                        type="button"
                        className={btnSecondary}
                        disabled={toggleBusyId === id}
                        onClick={() => onToggleActive(id, nextActive)}
                      >
                        {r.is_active ? "⏸ Приостановить" : "▶ Запустить"}
                      </button>
                    </td>
                    <td className="px-3 py-2 align-top">
                      <IconEditButton title="Редактировать расписание" onClick={() => openEditModal(r)} />
                    </td>
                    <td className="px-3 py-2 align-top">
                      <button
                        type="button"
                        className={btnSecondary}
                        onClick={() => triggerUpload(id)}
                      >
                        ⬆ Загрузить данные
                      </button>
                    </td>
                    <td className="px-3 py-2 align-top">
                      <IconDeleteButton title="Удалить расписание" onClick={() => onDelete(id)} />
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <input
        ref={uploadInputRef}
        type="file"
        id="sch-upload-input"
        accept=".csv,.json,application/json,text/csv"
        className="hidden"
        onChange={onUploadChange}
      />

      {editOpen && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 bg-black/60"
            aria-label="Закрыть"
            onClick={closeEditModal}
          />
          <div
            className="fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[min(100%-2rem,36rem)] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-xl border border-slate-600 bg-slate-900 shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="sch-edit-title"
          >
            <div className="flex items-start justify-between border-b border-slate-700 px-4 py-3">
              <h2
                id="sch-edit-title"
                className="text-lg font-semibold text-white"
              >
                Редактировать расписание
              </h2>
              <button
                type="button"
                className="text-2xl leading-none text-slate-400 hover:text-white"
                aria-label="Закрыть"
                onClick={closeEditModal}
              >
                ×
              </button>
            </div>
            <form
              id="sch-edit-form"
              className="max-h-[70vh] space-y-4 overflow-auto p-4"
              onSubmit={onEditSubmit}
            >
              <div>
                <label className={labelClass} htmlFor="sch-edit-chat-id">
                  chat_id (MAX)
                </label>
                <input
                  id="sch-edit-chat-id"
                  type="text"
                  className={inputClass}
                  required
                  value={edit.chatId}
                  onChange={(e) => setEditField("chatId", e.target.value)}
                />
              </div>
              <div>
                <label className={labelClass} htmlFor="sch-edit-type">
                  Тип триггера
                </label>
                <select
                  id="sch-edit-type"
                  className={inputClass}
                  value={edit.type}
                  onChange={(e) => setEditField("type", e.target.value)}
                >
                  <option value="DATABASE">DATABASE — по дате события</option>
                  <option value="INTERVAL">INTERVAL — повтор с интервалом</option>
                  <option value="REMINDER">REMINDER — напоминание</option>
                </select>
              </div>
              <div>
                <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-200">
                  <input
                    type="checkbox"
                    id="sch-edit-active"
                    className="h-4 w-4 rounded border-slate-500 bg-slate-900 accent-sky-500"
                    checked={edit.active}
                    onChange={(e) => setEditField("active", e.target.checked)}
                  />
                  Активно
                </label>
              </div>

              {showIntervalEdit && (
                <div
                  id="sch-edit-interval-block"
                  className="flex flex-wrap gap-3 rounded-lg border border-slate-700/60 bg-slate-800/40 p-3"
                >
                  <div className="min-w-[6rem] flex-1">
                    <label className={labelClass} htmlFor="sch-edit-days">
                      Дни
                    </label>
                    <input
                      id="sch-edit-days"
                      type="number"
                      min={0}
                      className={inputClass}
                      value={edit.days}
                      onChange={(e) => setEditField("days", e.target.value)}
                    />
                  </div>
                  <div className="min-w-[6rem] flex-1">
                    <label className={labelClass} htmlFor="sch-edit-hours">
                      Часы
                    </label>
                    <input
                      id="sch-edit-hours"
                      type="number"
                      min={0}
                      className={inputClass}
                      value={edit.hours}
                      onChange={(e) => setEditField("hours", e.target.value)}
                    />
                  </div>
                  <div className="min-w-[6rem] flex-1">
                    <label className={labelClass} htmlFor="sch-edit-minutes">
                      Минуты
                    </label>
                    <input
                      id="sch-edit-minutes"
                      type="number"
                      min={0}
                      className={inputClass}
                      value={edit.minutes}
                      onChange={(e) => setEditField("minutes", e.target.value)}
                    />
                  </div>
                </div>
              )}

              {showReminderEdit && (
                <div id="sch-edit-reminder-block">
                  <label className={labelClass} htmlFor="sch-edit-offset">
                    За сколько минут до события напомнить
                  </label>
                  <input
                    id="sch-edit-offset"
                    type="number"
                    min={0}
                    className={inputClass}
                    value={edit.offset}
                    onChange={(e) => setEditField("offset", e.target.value)}
                  />
                </div>
              )}

              {showDbHintEdit && (
                <p id="sch-edit-db-hint" className={helpClass}>
                  Для ежегодных дат в событиях:{" "}
                  <code className="text-xs">annual: true</code>. Время — по
                  Саратову, если без смещения в ISO.
                </p>
              )}

              <div>
                <label className={labelClass} htmlFor="sch-edit-prompt">
                  Доп. инструкции для LLM
                </label>
                <textarea
                  id="sch-edit-prompt"
                  className={`${inputClass} resize-y`}
                  rows={3}
                  value={edit.prompt}
                  onChange={(e) => setEditField("prompt", e.target.value)}
                />
              </div>
              <div>
                <label className={labelClass} htmlFor="sch-edit-content">
                  Шаблон / описание
                </label>
                <textarea
                  id="sch-edit-content"
                  className={`${inputClass} resize-y`}
                  rows={3}
                  value={edit.content}
                  onChange={(e) => setEditField("content", e.target.value)}
                />
              </div>
              <p
                id="sch-edit-msg"
                className={`min-h-[1.25rem] text-sm ${editMsgClass}`}
                aria-live="polite"
              >
                {editMsg}
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="submit"
                  className={btnPrimary}
                  id="sch-edit-save"
                  disabled={savingEdit}
                >
                  <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
                  Сохранить
                </button>
                <button
                  type="button"
                  className={btnSecondary}
                  id="sch-edit-cancel"
                  onClick={closeEditModal}
                >
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </>
      )}
    </div>
  );
}
