import { useCallback, useEffect, useState } from "react";
import { ClipboardList, Plus, Save } from "lucide-react";
import {
  IconCopyButton,
  IconDeleteButton,
  IconEditButton,
  IconOpenUrlButton,
} from "../components/ui/IconActionButtons.jsx";
import { createPortal } from "react-dom";
import api from "../api/client.js";
import { useAuthStore } from "../store/authStore.js";
import { SurveyTakeExperience } from "../components/questionnaires/SurveyTakeExperience.jsx";
import { BTN_ADD, BTN_SAVE, ICON_BTN } from "../styles/pageLayout.js";
import { formatDateTimeRu } from "../utils/dateTimeFormat.js";

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

function defaultOptionsForType(type) {
  if (type === "text") return [];
  return [
    { text: "Вариант А", score: 5 },
    { text: "Вариант Б", score: 3 },
  ];
}

/** randomUUID() только в secure context (HTTPS/localhost); на http://IP-VPS падает без полифилла. */
function newQuestionKey() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    try {
      return crypto.randomUUID();
    } catch {
      /* ignore */
    }
  }
  return `q-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

function emptyQuestion(order) {
  return {
    _key: newQuestionKey(),
    text: "",
    type: "single",
    order,
    min_score: 0,
    max_score: 10,
    options: defaultOptionsForType("single"),
  };
}

function validateBuilder(title, questions) {
  const t = title.trim();
  if (!t) return "Укажите название опросника.";
  for (let i = 0; i < questions.length; i += 1) {
    const q = questions[i];
    if (!q.text.trim()) return `Вопрос ${i + 1}: введите текст.`;
    const min = Number(q.min_score);
    const max = Number(q.max_score);
    if (Number.isNaN(min) || Number.isNaN(max) || max < min) {
      return `Вопрос ${i + 1}: некорректный диапазон min/max.`;
    }
    if (q.type === "single" || q.type === "multiple") {
      if (!q.options.length) return `Вопрос ${i + 1}: добавьте варианты ответа.`;
      for (let j = 0; j < q.options.length; j += 1) {
        const o = q.options[j];
        if (!o.text.trim()) return `Вопрос ${i + 1}, вариант ${j + 1}: введите текст.`;
        const sc = Number(o.score);
        if (Number.isNaN(sc)) return `Вопрос ${i + 1}, вариант ${j + 1}: укажите балл.`;
        if (sc < min || sc > max) {
          return `Вопрос ${i + 1}, вариант «${o.text.slice(0, 24)}»: балл ${sc} вне [${min}, ${max}].`;
        }
      }
    } else if (q.options?.length) {
      return `Вопрос ${i + 1}: текстовый вопрос не должен иметь варианты.`;
    }
  }
  return "";
}

function mapApiToForm(data) {
  const qs = [...(data.questions || [])].sort(
    (a, b) => a.order - b.order || String(a.id).localeCompare(String(b.id)),
  );
  return {
    title: data.title || "",
    llm_criteria: data.llm_criteria || "",
    questions: qs.map((q, idx) => ({
      _key: q.id,
      text: q.text,
      type: q.type,
      order: idx,
      min_score: q.min_score,
      max_score: q.max_score,
      options: (q.options || []).map((o) => ({
        text: o.text,
        score: o.score,
      })),
    })),
  };
}

/** Абсолютная ссылка на прохождение опроса без панели (мессенджеры, Битрикс и т.д.). */
function publicSurveyUrl(id) {
  if (typeof window === "undefined") return "";
  const path = `/survey/${id}`;
  return `${window.location.origin}${path}`;
}

function toPayload(form) {
  return {
    title: form.title.trim(),
    llm_criteria: form.llm_criteria.trim(),
    questions: form.questions.map((q, i) => ({
      text: q.text.trim(),
      type: q.type,
      order: i,
      min_score: Number(q.min_score),
      max_score: Number(q.max_score),
      options:
        q.type === "text"
          ? []
          : q.options.map((o) => ({
              text: o.text.trim(),
              score: Number(o.score),
            })),
    })),
  };
}

export function QuestionnairesPage() {
  const user = useAuthStore((s) => s.user);
  const settingsOrganizationId = useAuthStore((s) => s.settingsOrganizationId);

  const [rows, setRows] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listErr, setListErr] = useState("");

  const [builderOpen, setBuilderOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [builderErr, setBuilderErr] = useState("");
  const [form, setForm] = useState({
    title: "",
    llm_criteria: "",
    questions: [],
  });

  const [takeId, setTakeId] = useState(null);
  const [deleteId, setDeleteId] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [copiedRowId, setCopiedRowId] = useState(null);

  const loadList = useCallback(async () => {
    setListLoading(true);
    setListErr("");
    try {
      const { data } = await api.get("/questionnaires");
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error(e);
      setListErr(formatApiDetail(e) || "Не удалось загрузить список");
      setRows([]);
    } finally {
      setListLoading(false);
    }
  }, [settingsOrganizationId]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const openCreate = () => {
    setEditingId(null);
    setForm({
      title: "",
      llm_criteria: "",
      questions: [emptyQuestion(0)],
    });
    setBuilderErr("");
    setBuilderOpen(true);
  };

  const openEdit = async (id) => {
    setBuilderErr("");
    setBuilderOpen(true);
    setEditingId(id);
    try {
      const { data } = await api.get(`/questionnaires/${id}`);
      setForm(mapApiToForm(data));
    } catch (e) {
      console.error(e);
      setBuilderErr(formatApiDetail(e) || "Ошибка загрузки");
      setForm({ title: "", llm_criteria: "", questions: [] });
    }
  };

  const closeBuilder = () => {
    setBuilderOpen(false);
    setEditingId(null);
    setBuilderErr("");
  };

  const saveBuilder = async (ev) => {
    ev.preventDefault();
    const msg = validateBuilder(form.title, form.questions);
    if (msg) {
      setBuilderErr(msg);
      return;
    }
    setSaving(true);
    setBuilderErr("");
    try {
      const payload = toPayload(form);
      if (editingId) {
        await api.put(`/questionnaires/${editingId}`, payload);
      } else {
        await api.post("/questionnaires", payload);
      }
      closeBuilder();
      await loadList();
    } catch (e) {
      setBuilderErr(formatApiDetail(e) || "Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteId) return;
    setDeleting(true);
    try {
      await api.delete(`/questionnaires/${deleteId}`);
      setDeleteId(null);
      await loadList();
    } catch (e) {
      console.error(e);
      alert(formatApiDetail(e) || "Не удалось удалить");
    } finally {
      setDeleting(false);
    }
  };

  const updateQuestion = (idx, patch) => {
    setForm((prev) => {
      const questions = [...prev.questions];
      const cur = { ...questions[idx], ...patch };
      if (patch.type != null && patch.type !== questions[idx].type) {
        cur.options = defaultOptionsForType(patch.type);
      }
      questions[idx] = cur;
      return { ...prev, questions };
    });
  };

  const addQuestion = () => {
    setForm((prev) => ({
      ...prev,
      questions: [...prev.questions, emptyQuestion(prev.questions.length)],
    }));
  };

  const removeQuestion = (idx) => {
    setForm((prev) => ({
      ...prev,
      questions: prev.questions.filter((_, i) => i !== idx),
    }));
  };

  const updateOption = (qIdx, oIdx, patch) => {
    setForm((prev) => {
      const questions = [...prev.questions];
      const q = { ...questions[qIdx] };
      const options = [...q.options];
      options[oIdx] = { ...options[oIdx], ...patch };
      q.options = options;
      questions[qIdx] = q;
      return { ...prev, questions };
    });
  };

  const addOption = (qIdx) => {
    setForm((prev) => {
      const questions = [...prev.questions];
      const q = { ...questions[qIdx] };
      q.options = [...q.options, { text: "", score: q.min_score }];
      questions[qIdx] = q;
      return { ...prev, questions };
    });
  };

  const removeOption = (qIdx, oIdx) => {
    setForm((prev) => {
      const questions = [...prev.questions];
      const q = { ...questions[qIdx] };
      q.options = q.options.filter((_, i) => i !== oIdx);
      questions[qIdx] = q;
      return { ...prev, questions };
    });
  };

  const modalRoot = typeof document !== "undefined" ? document.body : null;

  return (
    <>
    <div className="w-full min-w-0 space-y-6 text-slate-100">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold text-white">
            <ClipboardList className="h-7 w-7 shrink-0 text-sky-400/90" strokeWidth={1.75} aria-hidden />
            Опросники
          </h1>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
        >
          Создать опросник
        </button>
      </div>

      {listErr ? <p className="text-sm text-red-400">{listErr}</p> : null}

      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/40">
        <table className="min-w-full text-left text-sm text-slate-300">
          <thead className="border-b border-slate-800 bg-slate-900/80 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Название</th>
              <th className="px-4 py-3 font-medium min-w-[12rem] max-w-xs">Публичная ссылка</th>
              <th className="px-4 py-3 font-medium">Создан</th>
              <th className="px-4 py-3 font-medium">Обновлён</th>
              <th className="px-4 py-3 font-medium text-right">Действия</th>
            </tr>
          </thead>
          <tbody>
            {listLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  Загрузка…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                  Нет опросников. Создайте первый.
                </td>
              </tr>
            ) : (
              rows.map((r) => {
                const pubUrl = publicSurveyUrl(r.id);
                return (
                <tr key={r.id} className="border-b border-slate-800/80 hover:bg-slate-800/30">
                  <td className="px-4 py-3 font-medium text-slate-200">{r.title}</td>
                  <td className="max-w-[min(22rem,40vw)] px-4 py-3 align-top">
                    <div className="flex flex-col gap-1.5">
                      <a
                        href={pubUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="truncate font-mono text-xs text-emerald-400 underline decoration-emerald-600/50 underline-offset-2 hover:text-emerald-300"
                        title={pubUrl}
                      >
                        {pubUrl}
                      </a>
                      <div className="flex flex-wrap items-center gap-1">
                        <IconCopyButton
                          title="Копировать ссылку"
                          copied={copiedRowId === r.id}
                          onClick={async () => {
                            try {
                              await navigator.clipboard.writeText(pubUrl);
                              setCopiedRowId(r.id);
                              window.setTimeout(() => setCopiedRowId((cur) => (cur === r.id ? null : cur)), 2000);
                            } catch {
                              window.prompt("Скопируйте ссылку:", pubUrl);
                            }
                          }}
                        />
                        <IconOpenUrlButton href={pubUrl} title="Открыть опросник" />
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{formatDateTimeRu(r.created_at)}</td>
                  <td className="px-4 py-3 text-slate-400">{formatDateTimeRu(r.updated_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex flex-wrap items-center justify-end gap-1">
                      <button
                        type="button"
                        className="rounded-md bg-slate-700 px-2.5 py-1 text-xs text-white hover:bg-slate-600"
                        onClick={() => setTakeId(r.id)}
                      >
                        Пройти
                      </button>
                      <IconEditButton title="Редактировать опросник" onClick={() => openEdit(r.id)} />
                      <IconDeleteButton title="Удалить опросник" onClick={() => setDeleteId(r.id)} />
                    </div>
                  </td>
                </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {builderOpen && modalRoot
        ? createPortal(
        <div className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto bg-black/60 p-4">
          <div className="my-8 w-full max-w-[100rem] rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">
                {editingId ? "Редактирование опросника" : "Новый опросник"}
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
            <form onSubmit={saveBuilder} className="space-y-5">
              <div>
                <label className="block text-xs font-medium text-slate-400">Название</label>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-emerald-600 focus:outline-none"
                  value={form.title}
                  onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                  placeholder="Например: Опрос удовлетворённости"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400">
                  Критерии оценки для ИИ
                </label>
                <textarea
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-emerald-600 focus:outline-none"
                  rows={4}
                  value={form.llm_criteria}
                  onChange={(e) => setForm((p) => ({ ...p, llm_criteria: e.target.value }))}
                  placeholder="Опишите, как ИИ должен интерпретировать ответы и баллы…"
                />
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-300">Вопросы</span>
                  <button
                    type="button"
                    className={`${BTN_ADD} text-sm`}
                    onClick={addQuestion}
                  >
                    <Plus className={ICON_BTN} strokeWidth={2} aria-hidden />
                    Добавить вопрос
                  </button>
                </div>
                {form.questions.map((q, qi) => (
                  <div
                    key={q._key}
                    className="rounded-lg border border-slate-800 bg-slate-950/50 p-4 space-y-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs text-slate-500">Вопрос {qi + 1}</span>
                      <select
                        className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                        value={q.type}
                        onChange={(e) => updateQuestion(qi, { type: e.target.value })}
                      >
                        <option value="single">Один вариант</option>
                        <option value="multiple">Несколько вариантов</option>
                        <option value="text">Свободный текст</option>
                      </select>
                      <IconDeleteButton
                        title="Удалить вопрос"
                        className="ml-auto h-7 w-7"
                        onClick={() => removeQuestion(qi)}
                      />
                    </div>
                    <input
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                      placeholder="Текст вопроса"
                      value={q.text}
                      onChange={(e) => updateQuestion(qi, { text: e.target.value })}
                    />
                    <div className="flex flex-wrap gap-3">
                      <label className="flex items-center gap-2 text-xs text-slate-400">
                        Min балл
                        <input
                          type="number"
                          step="any"
                          className="w-20 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-200"
                          value={q.min_score}
                          onChange={(e) => updateQuestion(qi, { min_score: e.target.value })}
                        />
                      </label>
                      <label className="flex items-center gap-2 text-xs text-slate-400">
                        Max балл
                        <input
                          type="number"
                          step="any"
                          className="w-20 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-200"
                          value={q.max_score}
                          onChange={(e) => updateQuestion(qi, { max_score: e.target.value })}
                        />
                      </label>
                    </div>
                    {q.type !== "text" ? (
                      <div className="space-y-2">
                        <div className="text-xs text-slate-500">Варианты (текст и балл в диапазоне вопроса)</div>
                        {q.options.map((o, oi) => (
                          <div key={oi} className="flex flex-wrap gap-2">
                            <input
                              className="min-w-[12rem] flex-1 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                              placeholder="Текст варианта"
                              value={o.text}
                              onChange={(e) => updateOption(qi, oi, { text: e.target.value })}
                            />
                            <input
                              type="number"
                              step="any"
                              className="w-24 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-200"
                              value={o.score}
                              onChange={(e) => updateOption(qi, oi, { score: e.target.value })}
                            />
                            <button
                              type="button"
                              className="text-xs text-slate-500 hover:text-red-400"
                              onClick={() => removeOption(qi, oi)}
                            >
                              ✕
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          className="text-xs text-emerald-500 hover:text-emerald-400"
                          onClick={() => addOption(qi)}
                        >
                          + Вариант
                        </button>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>

              {builderErr ? <p className="text-sm text-red-400">{builderErr}</p> : null}

              <div className="flex flex-wrap gap-2 border-t border-slate-800 pt-4">
                <button type="submit" disabled={saving} className={BTN_SAVE}>
                  <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
                  {saving ? "Сохранение…" : "Сохранить"}
                </button>
                <button
                  type="button"
                  className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
                  onClick={closeBuilder}
                >
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </div>,
        modalRoot,
      )
        : null}

      {takeId && modalRoot
        ? createPortal(
        <div className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto bg-black/60 p-4">
          <div className="my-8 w-full max-w-[100rem]">
            <SurveyTakeExperience questionnaireId={takeId} onClose={() => setTakeId(null)} />
          </div>
        </div>,
        modalRoot,
      )
        : null}

      {deleteId && modalRoot
        ? createPortal(
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-xl">
            <p className="text-sm text-slate-200">Удалить этот опросник? Действие необратимо.</p>
            <div className="mt-4 flex items-center gap-2">
              <IconDeleteButton
                title="Удалить опросник"
                disabled={deleting}
                busy={deleting}
                className="h-10 w-10"
                onClick={confirmDelete}
              />
              <button
                type="button"
                className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
                onClick={() => setDeleteId(null)}
              >
                Отмена
              </button>
            </div>
          </div>
        </div>,
        modalRoot,
      )
        : null}
    </div>
    </>
  );
}
