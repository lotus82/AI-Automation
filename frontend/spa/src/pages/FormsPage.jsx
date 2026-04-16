import { useCallback, useEffect, useMemo, useState } from "react";
import { FileText, GripVertical } from "lucide-react";
import { IconCopyButton, IconDeleteButton, IconEditButton } from "../components/ui/IconActionButtons.jsx";
import api from "../api/client.js";

/** Визуальный отклик: нажатие, фокус, плавные переходы */
const pressable =
  "transition duration-100 ease-out select-none " +
  "active:scale-[0.97] active:brightness-110 motion-reduce:transform-none motion-reduce:active:scale-100 " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/70 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950";

const pressableSubtle = `${pressable} hover:bg-slate-800/80`;

const pressableDanger = `${pressable} hover:bg-red-950/40 hover:border-red-700/60`;

const pressablePrimary = `${pressable} shadow-sm active:shadow-inner hover:brightness-110`;

const FIELD_TYPES = [
  { value: "short_text", label: "Короткий текст" },
  { value: "long_text", label: "Многострочный текст" },
  { value: "phone", label: "Телефон" },
  { value: "email", label: "Email" },
  { value: "number", label: "Число" },
  { value: "date", label: "Дата" },
  { value: "single_choice", label: "Один вариант" },
  { value: "multiple_choice", label: "Несколько вариантов" },
];

function formatApiDetail(err) {
  const body = err?.response?.data;
  const det = body?.detail;
  if (typeof det === "string") return det;
  if (Array.isArray(det)) {
    return det.map((x) => (typeof x === "object" && x != null ? x.msg ?? x : x)).join("; ");
  }
  if (det != null) return JSON.stringify(det);
  return err?.message ?? String(err);
}

function newFieldId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    try {
      return crypto.randomUUID();
    } catch {
      /* ignore */
    }
  }
  return `f-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/** UI: max | tg | vk → API max | telegram | vk; пусто — отключить уведомления */
function eventNotifyToApi(messengerUi, chatId) {
  const c = (chatId || "").trim();
  const m = (messengerUi || "").trim();
  if (!m || !c) return { notify_messenger: null, notify_chat_id: null };
  return {
    notify_messenger: m === "tg" ? "telegram" : m,
    notify_chat_id: c,
  };
}

const tabBtn = (active) =>
  `shrink-0 cursor-pointer whitespace-nowrap rounded-t-lg border px-3 py-2.5 text-sm font-medium transition duration-150 ease-out select-none sm:px-4 ${
    active
      ? "border-slate-600 border-b-transparent bg-slate-800/95 text-white shadow-[inset_0_2px_0_0_rgba(16,185,129,0.55)] ring-2 ring-emerald-500/35"
      : "border-transparent text-slate-400 hover:border-slate-700/80 hover:bg-slate-800/60 hover:text-slate-100 active:scale-[0.97] active:bg-slate-800/90 active:brightness-110"
  } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950`;

export function FormsPage() {
  const [tab, setTab] = useState("templates");
  const [templates, setTemplates] = useState([]);
  const [events, setEvents] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  const [tplName, setTplName] = useState("");
  const [tplDesc, setTplDesc] = useState("");
  const [tplFields, setTplFields] = useState([]);
  const [tplSaving, setTplSaving] = useState(false);
  const [tplMsg, setTplMsg] = useState("");
  const [editingTplId, setEditingTplId] = useState(null);

  const [evTitle, setEvTitle] = useState("");
  const [evSubtitle, setEvSubtitle] = useState("");
  const [evTemplateId, setEvTemplateId] = useState("");
  const [evStart, setEvStart] = useState("");
  const [evEnd, setEvEnd] = useState("");
  const [evDeadline, setEvDeadline] = useState("");
  const [evScheduleIds, setEvScheduleIds] = useState([]);
  const [evNotifyMessenger, setEvNotifyMessenger] = useState("");
  const [evNotifyChatId, setEvNotifyChatId] = useState("");
  const [evSaving, setEvSaving] = useState(false);
  const [evMsg, setEvMsg] = useState("");

  const [selectedEvent, setSelectedEvent] = useState(null);
  const [submissions, setSubmissions] = useState([]);
  const [subLoading, setSubLoading] = useState(false);
  const [extendDeadline, setExtendDeadline] = useState("");
  const [dragFieldIdx, setDragFieldIdx] = useState(null);
  const [dragOverFieldIdx, setDragOverFieldIdx] = useState(null);
  const [eventBusy, setEventBusy] = useState(null);
  const [copyUrlFlash, setCopyUrlFlash] = useState(false);
  const [deletingSubmissionId, setDeletingSubmissionId] = useState(null);
  const [editEvNotifyMessenger, setEditEvNotifyMessenger] = useState("");
  const [editEvNotifyChat, setEditEvNotifyChat] = useState("");
  const [editEvTitle, setEditEvTitle] = useState("");
  const [editEvSubtitle, setEditEvSubtitle] = useState("");
  const [editEvStart, setEditEvStart] = useState("");
  const [editEvEnd, setEditEvEnd] = useState("");

  const loadAll = useCallback(async () => {
    setErr("");
    try {
      const [tRes, eRes, sRes] = await Promise.all([
        api.get("/forms/templates"),
        api.get("/forms/events"),
        api.get("/schedules"),
      ]);
      setTemplates(tRes.data ?? []);
      setEvents(eRes.data ?? []);
      setSchedules(sRes.data ?? []);
    } catch (e) {
      setErr(formatApiDetail(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  /** Догружаем шаблон по id, если его нет в списке (иначе колонки ответов не строятся). */
  useEffect(() => {
    if (!selectedEvent?.form_template_id) return;
    const tid = String(selectedEvent.form_template_id);
    if (templates.some((t) => String(t.id) === tid)) return;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get(`/forms/templates/${tid}`);
        if (cancelled || !data?.id) return;
        setTemplates((prev) => {
          if (prev.some((p) => String(p.id) === String(data.id))) return prev;
          return [...prev, data];
        });
      } catch {
        /* 401/404 и т.д. — колонки строятся из ключей answers (fallback в useMemo) */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedEvent?.form_template_id, selectedEvent?.id, templates]);

  const loadSubmissions = async (eventId) => {
    setSubLoading(true);
    try {
      const { data } = await api.get(`/forms/events/${eventId}/submissions`);
      setSubmissions(data ?? []);
    } catch (e) {
      setErr(formatApiDetail(e));
    } finally {
      setSubLoading(false);
    }
  };

  useEffect(() => {
    if (selectedEvent?.id) {
      loadSubmissions(selectedEvent.id);
      const d = selectedEvent.registration_deadline_at;
      if (d) {
        const dt = new Date(d);
        if (!Number.isNaN(dt.getTime())) {
          const pad = (n) => String(n).padStart(2, "0");
          const local = `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
          setExtendDeadline(local);
        }
      }
    } else {
      setSubmissions([]);
    }
  }, [selectedEvent?.id, selectedEvent?.registration_deadline_at]);

  useEffect(() => {
    if (!selectedEvent) {
      setEditEvNotifyMessenger("");
      setEditEvNotifyChat("");
      return;
    }
    const m = selectedEvent.notify_messenger;
    setEditEvNotifyMessenger(m === "telegram" ? "tg" : m || "");
    setEditEvNotifyChat(selectedEvent.notify_chat_id ?? "");
  }, [selectedEvent?.id, selectedEvent?.notify_messenger, selectedEvent?.notify_chat_id]);

  useEffect(() => {
    if (!selectedEvent) {
      setEditEvTitle("");
      setEditEvSubtitle("");
      setEditEvStart("");
      setEditEvEnd("");
      return;
    }
    setEditEvTitle(selectedEvent.title ?? "");
    setEditEvSubtitle(selectedEvent.title_subtitle ?? "");
    setEditEvStart(selectedEvent.event_start_date ?? "");
    setEditEvEnd(selectedEvent.event_end_date ?? "");
  }, [
    selectedEvent?.id,
    selectedEvent?.title,
    selectedEvent?.title_subtitle,
    selectedEvent?.event_start_date,
    selectedEvent?.event_end_date,
  ]);

  const addField = () => {
    setTplFields((prev) => [
      ...prev,
      {
        id: newFieldId(),
        type: "short_text",
        label: "",
        required: false,
        placeholder: "",
        options: [],
        order: prev.length,
      },
    ]);
  };

  const updateField = (idx, patch) => {
    setTplFields((prev) => prev.map((f, i) => (i === idx ? { ...f, ...patch } : f)));
  };

  const removeField = (idx) => {
    setTplFields((prev) => prev.filter((_, i) => i !== idx).map((f, i) => ({ ...f, order: i })));
  };

  const reorderFields = (fromIdx, toIdx) => {
    if (fromIdx === toIdx || fromIdx < 0 || toIdx < 0) return;
    setTplFields((prev) => {
      const next = [...prev];
      const [item] = next.splice(fromIdx, 1);
      next.splice(toIdx, 0, item);
      return next.map((f, i) => ({ ...f, order: i }));
    });
  };

  const parseOptionsText = (text) =>
    String(text || "")
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

  const resetTemplateForm = () => {
    setEditingTplId(null);
    setTplName("");
    setTplDesc("");
    setTplFields([]);
    setTplMsg("");
  };

  const startEditTemplate = (t) => {
    setEditingTplId(t.id);
    setTplName(t.name);
    setTplDesc(t.description ?? "");
    setTplFields(
      (t.fields ?? []).map((f, i) => ({
        ...f,
        options: f.options ?? [],
        order: f.order ?? i,
      })),
    );
    setTab("templates");
  };

  const saveTemplate = async (e) => {
    e.preventDefault();
    setTplSaving(true);
    setTplMsg("");
    try {
      const fields = tplFields.map((f, i) => ({
        id: f.id,
        type: f.type,
        label: f.label.trim(),
        required: Boolean(f.required),
        placeholder: f.placeholder?.trim() || null,
        options: f.type === "single_choice" || f.type === "multiple_choice" ? f.options : [],
        order: i,
      }));
      for (const fld of fields) {
        if (!fld.label) {
          setTplMsg("У каждого поля должна быть подпись.");
          return;
        }
      }
      if (editingTplId) {
        await api.patch(`/forms/templates/${editingTplId}`, {
          name: tplName.trim(),
          description: tplDesc.trim(),
          fields,
        });
        setTplMsg("Шаблон сохранён.");
      } else {
        await api.post("/forms/templates", {
          name: tplName.trim(),
          description: tplDesc.trim(),
          fields,
        });
        setTplMsg("Шаблон создан.");
        resetTemplateForm();
      }
      await loadAll();
    } catch (err) {
      setTplMsg(`Ошибка: ${formatApiDetail(err)}`);
    } finally {
      setTplSaving(false);
    }
  };

  const deleteTemplate = async (id) => {
    if (!window.confirm("Удалить шаблон? Нельзя, если есть мероприятия с этой формой.")) return;
    try {
      await api.delete(`/forms/templates/${id}`);
      await loadAll();
      if (editingTplId === id) resetTemplateForm();
    } catch (err) {
      alert(formatApiDetail(err));
    }
  };

  const createEvent = async (e) => {
    e.preventDefault();
    if (!evTemplateId) {
      setEvMsg("Выберите шаблон формы.");
      return;
    }
    setEvSaving(true);
    setEvMsg("");
    try {
      const body = {
        title: evTitle.trim(),
        title_subtitle: evSubtitle.trim(),
        form_template_id: evTemplateId,
        event_start_date: evStart,
        event_end_date: evEnd,
        schedule_ids: evScheduleIds,
      };
      if (evDeadline.trim()) {
        const d = new Date(evDeadline);
        if (!Number.isNaN(d.getTime())) body.registration_deadline_at = d.toISOString();
      }
      Object.assign(body, eventNotifyToApi(evNotifyMessenger, evNotifyChatId));
      await api.post("/forms/events", body);
      setEvTitle("");
      setEvSubtitle("");
      setEvDeadline("");
      setEvScheduleIds([]);
      setEvNotifyMessenger("");
      setEvNotifyChatId("");
      setEvMsg("Мероприятие создано.");
      await loadAll();
    } catch (err) {
      setEvMsg(`Ошибка: ${formatApiDetail(err)}`);
    } finally {
      setEvSaving(false);
    }
  };

  const deleteEvent = async (id) => {
    if (!window.confirm("Удалить мероприятие и все ответы?")) return;
    setEventBusy("delete");
    try {
      await api.delete(`/forms/events/${id}`);
      if (selectedEvent?.id === id) setSelectedEvent(null);
      await loadAll();
    } catch (err) {
      alert(formatApiDetail(err));
    } finally {
      setEventBusy(null);
    }
  };

  const patchEvent = async (id, body, busyKey = "patch") => {
    setEventBusy(busyKey);
    try {
      await api.patch(`/forms/events/${id}`, body);
      await loadAll();
      const { data } = await api.get(`/forms/events/${id}`);
      setSelectedEvent(data);
    } catch (err) {
      alert(formatApiDetail(err));
    } finally {
      setEventBusy(null);
    }
  };

  const deleteSubmission = async (submissionId) => {
    if (!selectedEvent?.id) return;
    if (!window.confirm("Удалить эту заявку из списка? Действие необратимо.")) return;
    setDeletingSubmissionId(submissionId);
    try {
      await api.delete(`/forms/events/${selectedEvent.id}/submissions/${submissionId}`);
      setSubmissions((prev) => prev.filter((s) => s.id !== submissionId));
      await loadAll();
      const { data } = await api.get(`/forms/events/${selectedEvent.id}`);
      setSelectedEvent(data);
    } catch (err) {
      alert(formatApiDetail(err));
    } finally {
      setDeletingSubmissionId(null);
    }
  };

  const exportXlsx = async (eventId) => {
    setEventBusy("xlsx");
    try {
      const res = await api.get(`/forms/events/${eventId}/export.xlsx`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `registration-${eventId}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(formatApiDetail(err));
    } finally {
      setEventBusy(null);
    }
  };

  const publicUrl = (eventId) => `${window.location.origin}/public/register/${eventId}`;

  const copyPublicUrl = async () => {
    if (!selectedEvent?.id) return;
    const url = publicUrl(selectedEvent.id);
    try {
      await navigator.clipboard.writeText(url);
      setCopyUrlFlash(true);
      window.setTimeout(() => setCopyUrlFlash(false), 1400);
    } catch {
      alert("Не удалось скопировать в буфер обмена.");
    }
  };

  const submissionColumns = useMemo(() => {
    if (!selectedEvent) return [];
    const tid = String(selectedEvent.form_template_id);
    const t = templates.find((x) => String(x.id) === tid);
    let fields = [...(t?.fields ?? [])].sort(
      (a, b) => (a.order ?? 0) - (b.order ?? 0) || String(a.id).localeCompare(String(b.id)),
    );
    if (fields.length === 0 && submissions.length > 0) {
      const ids = new Set();
      for (const s of submissions) {
        let a = s.answers;
        if (typeof a === "string") {
          try {
            a = JSON.parse(a);
          } catch {
            a = {};
          }
        }
        Object.keys(a || {}).forEach((k) => ids.add(k));
      }
      fields = [...ids]
        .sort()
        .map((id) => ({ id, label: id, order: 0, type: "short_text", required: false, options: [] }));
    }
    return fields;
  }, [selectedEvent, templates, submissions]);

  return (
    <div className="w-full min-w-0 space-y-6 text-slate-100">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-white">
          <FileText className="h-8 w-8 shrink-0 text-sky-400/90" strokeWidth={1.75} aria-hidden />
          Формы
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Конструктор форм (регистрация, обратная связь), мероприятия с отдельными ссылками и сбором ответов в БД.
        </p>
      </div>

      {err ? (
        <p className="rounded-lg border border-red-900/40 bg-red-950/20 px-3 py-2 text-sm text-red-200">{err}</p>
      ) : null}

      <div className="mb-0 flex flex-nowrap gap-1 overflow-x-auto overscroll-x-contain border-b border-slate-700/80 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <button type="button" className={tabBtn(tab === "templates")} onClick={() => setTab("templates")}>
          Шаблоны форм
        </button>
        <button type="button" className={tabBtn(tab === "events")} onClick={() => setTab("events")}>
          Мероприятия
        </button>
      </div>

      {loading ? <p className="text-slate-400">Загрузка…</p> : null}

      {!loading && tab === "templates" ? (
        <div className="grid gap-8 lg:grid-cols-2">
          <section>
            <h2 className="mb-3 text-lg font-semibold text-slate-200">
              {editingTplId ? "Редактирование шаблона" : "Новый шаблон"}
            </h2>
            <form className="space-y-4 rounded-xl border border-slate-700/80 bg-slate-900/50 p-5" onSubmit={saveTemplate}>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">Название шаблона</label>
                <input
                  className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                  value={tplName}
                  onChange={(e) => setTplName(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-400">Описание (внутреннее)</label>
                <input
                  className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                  value={tplDesc}
                  onChange={(e) => setTplDesc(e.target.value)}
                />
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <span className="text-sm font-medium text-slate-300">Поля формы</span>
                    <p className="text-xs text-slate-500">Меняйте порядок, перетаскивая блок за иконку слева.</p>
                  </div>
                  <button
                    type="button"
                    className={`rounded border border-slate-600 px-2 py-1 text-xs text-sky-300 ${pressableSubtle}`}
                    onClick={addField}
                  >
                    + Поле
                  </button>
                </div>
                {tplFields.map((f, idx) => (
                  <div
                    key={f.id}
                    className={`rounded-lg border bg-slate-950/60 p-3 transition-shadow ${
                      dragFieldIdx === idx ? "border-emerald-600/50 opacity-70 shadow-md" : "border-slate-700"
                    } ${
                      dragOverFieldIdx === idx && dragFieldIdx !== null && dragFieldIdx !== idx
                        ? "ring-2 ring-emerald-500/80 ring-offset-2 ring-offset-slate-950 border-emerald-500/40"
                        : ""
                    } space-y-2`}
                    onDragOver={(e) => {
                      e.preventDefault();
                      e.dataTransfer.dropEffect = "move";
                      if (dragFieldIdx !== null) setDragOverFieldIdx(idx);
                    }}
                    onDragLeave={(e) => {
                      if (!e.currentTarget.contains(e.relatedTarget)) setDragOverFieldIdx(null);
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      const raw = e.dataTransfer.getData("text/plain");
                      const from = parseInt(raw, 10);
                      setDragOverFieldIdx(null);
                      setDragFieldIdx(null);
                      if (!Number.isNaN(from)) reorderFields(from, idx);
                    }}
                  >
                    <div className="flex gap-2">
                      <button
                        type="button"
                        draggable
                        onDragStart={(e) => {
                          e.dataTransfer.setData("text/plain", String(idx));
                          e.dataTransfer.effectAllowed = "move";
                          setDragFieldIdx(idx);
                        }}
                        onDragEnd={() => {
                          setDragFieldIdx(null);
                          setDragOverFieldIdx(null);
                        }}
                        className={`mt-0.5 h-fit shrink-0 rounded border border-slate-600 bg-slate-800/90 p-1.5 text-slate-400 hover:text-emerald-300 cursor-grab active:cursor-grabbing ${pressableSubtle}`}
                        aria-label="Перетащить поле"
                        title="Перетащить"
                      >
                        <GripVertical className="h-4 w-4" strokeWidth={2} aria-hidden />
                      </button>
                      <div className="min-w-0 flex-1 space-y-2">
                        <div className="flex flex-wrap gap-2">
                          <select
                            className="rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-white"
                            value={f.type}
                            onChange={(e) => updateField(idx, { type: e.target.value })}
                          >
                            {FIELD_TYPES.map((o) => (
                              <option key={o.value} value={o.value}>
                                {o.label}
                              </option>
                            ))}
                          </select>
                          <label className="flex items-center gap-1 text-xs text-slate-400">
                            <input
                              type="checkbox"
                              checked={f.required}
                              onChange={(e) => updateField(idx, { required: e.target.checked })}
                            />
                            Обязательное
                          </label>
                          <IconDeleteButton
                            title="Удалить поле"
                            className={`ml-auto h-7 w-7 ${pressableDanger}`}
                            onClick={() => removeField(idx)}
                          />
                        </div>
                        <input
                          className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-sm text-white"
                          placeholder="Подпись поля"
                          value={f.label}
                          onChange={(e) => updateField(idx, { label: e.target.value })}
                        />
                        <input
                          className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-300"
                          placeholder="Подсказка (placeholder)"
                          value={f.placeholder ?? ""}
                          onChange={(e) => updateField(idx, { placeholder: e.target.value })}
                        />
                        {(f.type === "single_choice" || f.type === "multiple_choice") && (
                          <textarea
                            className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-300"
                            rows={3}
                            placeholder="Варианты — по одному в строке"
                            value={(f.options ?? []).join("\n")}
                            onChange={(e) => updateField(idx, { options: parseOptionsText(e.target.value) })}
                          />
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="submit"
                  disabled={tplSaving}
                  className={`rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50 disabled:active:scale-100 ${pressablePrimary}`}
                >
                  {editingTplId ? "Сохранить" : "Создать шаблон"}
                </button>
                {editingTplId ? (
                  <button
                    type="button"
                    className={`rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 ${pressableSubtle}`}
                    onClick={resetTemplateForm}
                  >
                    Отмена
                  </button>
                ) : null}
              </div>
              {tplMsg ? <p className="text-sm text-slate-400">{tplMsg}</p> : null}
            </form>
          </section>
          <section>
            <h2 className="mb-3 text-lg font-semibold text-slate-200">Сохранённые шаблоны</h2>
            <ul className="space-y-2">
              {templates.map((t) => (
                <li
                  key={t.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-700 bg-slate-900/40 px-3 py-2"
                >
                  <div>
                    <div className="font-medium text-white">{t.name}</div>
                    <div className="text-xs text-slate-500">{(t.fields ?? []).length} полей</div>
                  </div>
                  <div className="flex items-center gap-1">
                    <IconEditButton
                      title="Изменить шаблон"
                      className={pressableSubtle}
                      onClick={() => startEditTemplate(t)}
                    />
                    <IconDeleteButton
                      title="Удалить шаблон"
                      className={pressableDanger}
                      onClick={() => deleteTemplate(t.id)}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      ) : null}

      {!loading && tab === "events" ? (
        <div className="grid gap-8 lg:grid-cols-2">
          <section>
            <h2 className="mb-3 text-lg font-semibold text-slate-200">Новое мероприятие</h2>
            <form className="space-y-4 rounded-xl border border-slate-700/80 bg-slate-900/50 p-5" onSubmit={createEvent}>
              <div>
                <label className="mb-1 block text-xs text-slate-400">Заголовок (крупно на странице регистрации)</label>
                <input
                  className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                  value={evTitle}
                  onChange={(e) => setEvTitle(e.target.value)}
                  required
                  placeholder="Например: Пенуэл Пробуждения — Саратов"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Дополнительный текст (обычный шрифт: ссылки на чаты, примечания)
                </label>
                <textarea
                  className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                  rows={4}
                  value={evSubtitle}
                  onChange={(e) => setEvSubtitle(e.target.value)}
                  placeholder="Обязательный вопрос, группа: https://t.me/…"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-400">Шаблон формы</label>
                <select
                  className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                  value={evTemplateId}
                  onChange={(e) => setEvTemplateId(e.target.value)}
                  required
                >
                  <option value="">— выберите —</option>
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs text-slate-400">Дата начала</label>
                  <input
                    type="date"
                    className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                    value={evStart}
                    onChange={(e) => setEvStart(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">Дата окончания</label>
                  <input
                    type="date"
                    className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                    value={evEnd}
                    onChange={(e) => setEvEnd(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-400">
                  Дедлайн регистрации (необязательно; по умолчанию — конец последнего дня мероприятия)
                </label>
                <input
                  type="datetime-local"
                  className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                  value={evDeadline}
                  onChange={(e) => setEvDeadline(e.target.value)}
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs text-slate-400">Уведомления о регистрациях — мессенджер</label>
                  <select
                    className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                    value={evNotifyMessenger}
                    onChange={(e) => setEvNotifyMessenger(e.target.value)}
                  >
                    <option value="">— не отправлять —</option>
                    <option value="max">MAX</option>
                    <option value="tg">Telegram</option>
                    <option value="vk">VK</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-400">ID чата</label>
                  <input
                    className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white disabled:opacity-50"
                    value={evNotifyChatId}
                    onChange={(e) => setEvNotifyChatId(e.target.value)}
                    placeholder="chat id / peer id"
                    disabled={!evNotifyMessenger}
                  />
                </div>
              </div>
              <p className="text-xs text-slate-500">
                При новой заявке бот отправит в этот чат данные участника и общее число зарегистрированных. Нужны токены на
                сервере: MAX_BOT_TOKEN, TELEGRAM_BOT_TOKEN или VK_API_ACCESS_TOKEN.
              </p>
              <div>
                <label className="mb-1 block text-xs text-slate-400">Расписания (напоминания), привязка к мероприятию</label>
                <select
                  multiple
                  className="h-28 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                  value={evScheduleIds}
                  onChange={(e) => {
                    const opts = [...e.target.selectedOptions].map((o) => o.value);
                    setEvScheduleIds(opts);
                  }}
                >
                  {schedules.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.type} · {s.chat_id.slice(0, 12)}…
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-slate-500">
                  Удерживайте Ctrl (Cmd на Mac) для выбора нескольких. Создание расписаний — в разделе «Расписание».
                </p>
              </div>
              <button
                type="submit"
                disabled={evSaving}
                className={`rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50 disabled:active:scale-100 ${pressablePrimary}`}
              >
                Создать мероприятие
              </button>
              {evMsg ? <p className="text-sm text-slate-400">{evMsg}</p> : null}
            </form>
          </section>
          <section className="min-w-0 space-y-4">
            <h2 className="text-lg font-semibold text-slate-200">Список мероприятий</h2>
            <div className="overflow-x-auto rounded-xl border border-slate-700/80">
              <table className="w-full min-w-[560px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-700 bg-slate-900/60 text-xs uppercase text-slate-400">
                    <th className="px-3 py-2">Название</th>
                    <th className="px-3 py-2">Даты</th>
                    <th className="px-3 py-2">Открыта</th>
                    <th className="px-3 py-2">Заявок</th>
                    <th className="px-3 py-2 w-24"> </th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((ev) => (
                    <tr key={ev.id} className="border-b border-slate-800 hover:bg-slate-800/30">
                      <td className="px-3 py-2 text-slate-200">{ev.title}</td>
                      <td className="px-3 py-2 text-slate-400 whitespace-nowrap">
                        {ev.event_start_date} — {ev.event_end_date}
                      </td>
                      <td className="px-3 py-2">{ev.registration_open ? "да" : "нет"}</td>
                      <td className="px-3 py-2">{ev.submissions_count}</td>
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          className={`rounded px-2 py-1 text-sky-400 border border-sky-800/30 ${pressableSubtle}`}
                          onClick={() => setSelectedEvent(ev)}
                        >
                          Подробнее
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {selectedEvent ? (
              <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-4 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1 space-y-2">
                    <p className="text-xs text-slate-500">Шаблон: {selectedEvent.form_template_name}</p>
                    <p className="text-xs text-slate-500">
                      Регистрация: {selectedEvent.registration_open ? "открыта" : "закрыта"} · Заявок:{" "}
                      {selectedEvent.submissions_count}
                    </p>
                  </div>
                  <button
                    type="button"
                    className={`text-xs text-slate-400 border border-slate-600 rounded px-2 py-1 ${pressableSubtle}`}
                    onClick={() => setSelectedEvent(null)}
                  >
                    Закрыть
                  </button>
                </div>
                <div className="rounded-lg border border-slate-700/80 bg-slate-950/40 p-3 space-y-2">
                  <p className="text-xs font-medium text-slate-300">Название и даты мероприятия</p>
                  <label className="block text-xs text-slate-400">Заголовок (крупно)</label>
                  <input
                    className="w-full rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
                    value={editEvTitle}
                    onChange={(e) => setEditEvTitle(e.target.value)}
                  />
                  <label className="block text-xs text-slate-400">Дополнительный текст</label>
                  <textarea
                    className="w-full rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
                    rows={4}
                    value={editEvSubtitle}
                    onChange={(e) => setEditEvSubtitle(e.target.value)}
                    placeholder="Ссылки, примечания…"
                  />
                  <div className="grid gap-2 sm:grid-cols-2">
                    <div>
                      <label className="block text-xs text-slate-400">Дата начала</label>
                      <input
                        type="date"
                        className="w-full rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
                        value={editEvStart}
                        onChange={(e) => setEditEvStart(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-400">Дата окончания</label>
                      <input
                        type="date"
                        className="w-full rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-white"
                        value={editEvEnd}
                        onChange={(e) => setEditEvEnd(e.target.value)}
                      />
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={eventBusy === "meta" || !editEvTitle.trim()}
                    className={`rounded bg-emerald-800 px-3 py-1.5 text-xs text-white border border-emerald-700 ${pressablePrimary} disabled:opacity-50`}
                    onClick={() => {
                      if (!editEvTitle.trim()) return;
                      if (editEvEnd < editEvStart) {
                        alert("Дата окончания не может быть раньше даты начала.");
                        return;
                      }
                      patchEvent(
                        selectedEvent.id,
                        {
                          title: editEvTitle.trim(),
                          title_subtitle: editEvSubtitle.trim(),
                          event_start_date: editEvStart,
                          event_end_date: editEvEnd,
                        },
                        "meta",
                      );
                    }}
                  >
                    {eventBusy === "meta" ? "Сохранение…" : "Сохранить название и даты"}
                  </button>
                </div>
                <div>
                  <label className="text-xs text-slate-400">Публичная ссылка</label>
                  <div className="mt-1 flex flex-wrap gap-2">
                    <input
                      readOnly
                      className="min-w-0 flex-1 rounded border border-slate-600 bg-slate-950 px-2 py-1 text-xs text-slate-300"
                      value={publicUrl(selectedEvent.id)}
                    />
                    <IconCopyButton
                      title="Копировать публичную ссылку"
                      disabled={eventBusy === "copy"}
                      busy={eventBusy === "copy"}
                      copied={copyUrlFlash}
                      className={pressableSubtle}
                      onClick={() => {
                        setEventBusy("copy");
                        copyPublicUrl().finally(() => setEventBusy(null));
                      }}
                    />
                  </div>
                </div>
                <div className="rounded-lg border border-slate-700/80 bg-slate-950/40 p-3 space-y-2">
                  <p className="text-xs font-medium text-slate-300">Уведомления в чат о новых регистрациях</p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <select
                      className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-xs text-white"
                      value={editEvNotifyMessenger}
                      onChange={(e) => setEditEvNotifyMessenger(e.target.value)}
                    >
                      <option value="">— не отправлять —</option>
                      <option value="max">MAX</option>
                      <option value="tg">Telegram</option>
                      <option value="vk">VK</option>
                    </select>
                    <input
                      className="rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-xs text-white disabled:opacity-50"
                      value={editEvNotifyChat}
                      onChange={(e) => setEditEvNotifyChat(e.target.value)}
                      placeholder="ID чата"
                      disabled={!editEvNotifyMessenger}
                    />
                  </div>
                  <button
                    type="button"
                    disabled={eventBusy === "notify"}
                    className={`rounded bg-slate-700 px-3 py-1.5 text-xs text-white border border-slate-600 ${pressablePrimary} disabled:opacity-50`}
                    onClick={() =>
                      patchEvent(selectedEvent.id, eventNotifyToApi(editEvNotifyMessenger, editEvNotifyChat), "notify")
                    }
                  >
                    {eventBusy === "notify" ? "Сохранение…" : "Сохранить уведомления"}
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={!!eventBusy}
                    className={`rounded bg-slate-700 px-3 py-1.5 text-xs text-white border border-slate-600 ${pressablePrimary} disabled:active:scale-100`}
                    onClick={() => exportXlsx(selectedEvent.id)}
                  >
                    {eventBusy === "xlsx" ? "Скачивание…" : "Скачать XLSX"}
                  </button>
                  {selectedEvent.registration_closed_early ? (
                    <button
                      type="button"
                      disabled={!!eventBusy}
                      className={`rounded border border-emerald-700 px-3 py-1.5 text-xs text-emerald-300 ${pressableSubtle} disabled:opacity-50`}
                      onClick={() => patchEvent(selectedEvent.id, { registration_closed_early: false }, "reopen")}
                    >
                      {eventBusy === "reopen" ? "…" : "Снова открыть регистрацию"}
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={!!eventBusy}
                      className={`rounded border border-amber-700 px-3 py-1.5 text-xs text-amber-200 ${pressableSubtle} disabled:opacity-50`}
                      onClick={() => patchEvent(selectedEvent.id, { registration_closed_early: true }, "close")}
                    >
                      {eventBusy === "close" ? "…" : "Завершить регистрацию"}
                    </button>
                  )}
                  <IconDeleteButton
                    title="Удалить мероприятие"
                    disabled={!!eventBusy}
                    busy={eventBusy === "delete"}
                    className={`${pressableDanger} disabled:opacity-50`}
                    onClick={() => deleteEvent(selectedEvent.id)}
                  />
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <div>
                    <label className="block text-xs text-slate-400">Продлить дедлайн</label>
                    <input
                      type="datetime-local"
                      className="rounded border border-slate-600 bg-slate-950 px-2 py-1 text-xs text-white"
                      value={extendDeadline}
                      onChange={(e) => setExtendDeadline(e.target.value)}
                    />
                  </div>
                  <button
                    type="button"
                    disabled={!!eventBusy}
                    className={`rounded bg-emerald-700 px-3 py-1.5 text-xs text-white border border-emerald-600 ${pressablePrimary} disabled:opacity-50`}
                    onClick={() => {
                      const d = new Date(extendDeadline);
                      if (Number.isNaN(d.getTime())) return;
                      patchEvent(
                        selectedEvent.id,
                        {
                          registration_deadline_at: d.toISOString(),
                          registration_closed_early: false,
                        },
                        "deadline",
                      );
                    }}
                  >
                    {eventBusy === "deadline" ? "Сохранение…" : "Сохранить дедлайн"}
                  </button>
                </div>
                <h4 className="text-sm font-medium text-slate-300">Ответы</h4>
                {subLoading ? (
                  <p className="text-xs text-slate-500">Загрузка…</p>
                ) : submissions.length === 0 ? (
                  <p className="text-xs text-slate-500">Пока нет заявок.</p>
                ) : (
                  <div className="overflow-x-auto max-h-80 overflow-y-auto rounded border border-slate-700">
                    <table className="w-full min-w-[480px] text-xs">
                      <thead className="sticky top-0 z-[1] bg-slate-900 shadow-[0_1px_0_0_rgb(51_65_85)]">
                        <tr className="text-left text-slate-400">
                          <th className="w-36 shrink-0 px-2 py-1 align-top whitespace-nowrap">Время</th>
                          {submissionColumns.map((c) => (
                            <th
                              key={c.id}
                              className="max-w-[7rem] px-2 py-1 align-top font-medium"
                              title={c.label}
                            >
                              <span className="block max-w-[7rem] truncate">{c.label}</span>
                            </th>
                          ))}
                          <th className="w-10 shrink-0 px-2 py-1 align-top text-right text-slate-500 font-normal">
                            <span className="sr-only">Удалить</span>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {submissions.map((s) => (
                          <tr key={s.id} className="border-t border-slate-800">
                            <td className="px-2 py-1 align-top whitespace-nowrap text-slate-500">
                              {new Date(s.submitted_at).toLocaleString("ru-RU")}
                            </td>
                            {submissionColumns.map((c) => {
                              let ans = s.answers;
                              if (typeof ans === "string") {
                                try {
                                  ans = JSON.parse(ans);
                                } catch {
                                  ans = {};
                                }
                              }
                              const raw = ans?.[c.id];
                              const cell = Array.isArray(raw) ? raw.join("; ") : raw ?? "";
                              const str = cell === null || cell === undefined ? "" : String(cell);
                              return (
                                <td
                                  key={c.id}
                                  className="max-w-[14rem] break-words px-2 py-1 align-top text-slate-300"
                                  title={str || undefined}
                                >
                                  {str.trim() === "" ? "—" : str}
                                </td>
                              );
                            })}
                            <td className="px-1 py-1 align-top text-right">
                              <IconDeleteButton
                                title="Удалить заявку"
                                disabled={!!eventBusy || deletingSubmissionId !== null}
                                className={`h-7 w-7 ${pressableDanger}`}
                                onClick={() => deleteSubmission(s.id)}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ) : null}
          </section>
        </div>
      ) : null}
    </div>
  );
}
