import { AlertCircle, ArrowLeft, ChevronLeft, ChevronRight, Loader2, Save, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import api from "../../api/client.js";
import { useAuthStore } from "../../store/authStore.js";
import { BTN_SAVE, PAGE_H1, PAGE_HEADER_BETWEEN, PAGE_INNER, PAGE_SHELL, PAGE_TEXT } from "../../styles/pageLayout.js";

function formatApiDetail(d) {
  if (d == null) return "";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d
      .map((item) => (typeof item === "string" ? item : item?.msg ? String(item.msg) : JSON.stringify(item)))
      .filter(Boolean)
      .join("; ");
  }
  if (typeof d === "object") return d.message ? String(d.message) : JSON.stringify(d);
  return String(d);
}

const DOCUMENT_TYPES = [
  { value: "protocol_director_change", label: "Протокол о смене директора" },
  { value: "notice_fns", label: "Уведомление в ФНС" },
];

const inputBase =
  "w-full rounded-lg border bg-slate-950/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-600/60 border-slate-600";

const ringError = "ring-2 ring-red-500 ring-offset-2 ring-offset-slate-950 border-red-500";

/** Поле с красной рамкой при ошибке; тултип с текстом ошибки показывается при hover/focus-within группы (значение в поле не очищается). */
function ValidatedControl({ error, label, htmlFor, children }) {
  return (
    <div className="group relative space-y-1">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-300">
        {label}
      </label>
      <div className="relative">
        {children}
        {error ? (
          <div
            id={`${htmlFor}-err-tip`}
            role="tooltip"
            className="pointer-events-none absolute left-0 top-full z-30 mt-1 max-w-md rounded-md border border-red-600 bg-red-950 px-2.5 py-1.5 text-xs text-red-50 shadow-xl opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
          >
            {error}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function validateStep2({ agenda, attendeesText, meetingDate }) {
  const errors = {};

  const ag = agenda.trim();
  if (ag.length < 3) {
    errors.agenda = "Заполните повестку заседания (не менее 3 символов).";
  }

  const lines = attendeesText
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  if (lines.length === 0) {
    errors.attendeesText = "Укажите хотя бы одного участника (по одному ФИО на строку).";
  }

  if (meetingDate.trim()) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(meetingDate.trim())) {
      errors.meetingDate = "Дата должна быть в формате ГГГГ-ММ-ДД.";
    }
  }

  return errors;
}

export function DocumentWizardPage() {
  const user = useAuthStore((s) => s.user);
  const role = user?.role;
  const canAccess = role === "super_admin" || role === "org_admin" || role === "director";

  const [step, setStep] = useState(1);
  const [docType, setDocType] = useState(DOCUMENT_TYPES[0]?.value || "protocol_director_change");

  const [meetingDate, setMeetingDate] = useState("");
  const [agenda, setAgenda] = useState("");
  const [attendeesText, setAttendeesText] = useState("");

  const [fieldErrors, setFieldErrors] = useState({});

  const [genTrigger, setGenTrigger] = useState(0);
  const [genLoading, setGenLoading] = useState(false);
  const [genError, setGenError] = useState("");
  const [content, setContent] = useState("");
  const [documentId, setDocumentId] = useState(null);
  const [saveStatus, setSaveStatus] = useState("");
  const [saving, setSaving] = useState(false);

  const runGeneration = useCallback(async () => {
    const attendeesList = attendeesText
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

    const context = {
      agenda: agenda.trim(),
      attendees: attendeesList,
      meeting_date: meetingDate.trim() || undefined,
    };

    setGenLoading(true);
    setGenError("");
    setSaveStatus("");
    try {
      const { data } = await api.post("/compliance/documents/generate", {
        type: docType,
        context,
      });
      setContent(typeof data?.content === "string" ? data.content : "");
      setDocumentId(data?.document_id ?? null);
    } catch (e) {
      setGenError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
      setContent("");
      setDocumentId(null);
    } finally {
      setGenLoading(false);
    }
  }, [agenda, attendeesText, docType, meetingDate]);

  useEffect(() => {
    if (step !== 3 || genTrigger === 0) return;
    runGeneration();
  }, [step, genTrigger, runGeneration]);

  const goStep2 = () => {
    setFieldErrors({});
    setStep(2);
  };

  const goStep3 = () => {
    const errors = validateStep2({ agenda, attendeesText, meetingDate });
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    setGenTrigger((n) => n + 1);
    setStep(3);
  };

  const saveEdits = async () => {
    if (!documentId) return;
    setSaving(true);
    setSaveStatus("");
    try {
      await api.put(`/compliance/documents/${documentId}`, { content });
      setSaveStatus("Изменения сохранены.");
    } catch (e) {
      setSaveStatus(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    } finally {
      setSaving(false);
    }
  };

  if (!user) return null;
  if (!canAccess) return <Navigate to="/scenarios/qa-analytics" replace />;

  return (
    <div className={`${PAGE_SHELL} ${PAGE_INNER} space-y-6 px-4 py-6 sm:px-6`}>
      <div className={PAGE_HEADER_BETWEEN}>
        <div className="flex items-center gap-3">
          <Link
            to="/compliance"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-600 px-2 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden />
            К дашборду
          </Link>
          <h1 className={`${PAGE_H1} ${PAGE_TEXT}`}>Мастер документа</h1>
        </div>
        <div className="flex items-center gap-1 text-xs text-slate-500">
          {[1, 2, 3].map((n) => (
            <span key={n} className="flex items-center gap-1">
              {n > 1 ? <span className="text-slate-600">—</span> : null}
              <span
                className={`rounded-full px-2 py-0.5 ${
                  step === n ? "bg-emerald-600 text-white" : step > n ? "bg-slate-700 text-slate-300" : "bg-slate-800 text-slate-500"
                }`}
              >
                Шаг {n}
              </span>
            </span>
          ))}
        </div>
      </div>

      {step === 1 && (
        <div className="max-w-xl space-y-6 rounded-xl border border-slate-700 bg-slate-900/50 p-6">
          <h2 className="text-lg font-medium text-white">Выбор типа документа</h2>
          <div className="space-y-1">
            <label htmlFor="doc-type" className="block text-sm font-medium text-slate-300">
              Тип
            </label>
            <select
              id="doc-type"
              className={inputBase}
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
            >
              {DOCUMENT_TYPES.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end">
            <button
              type="button"
              onClick={goStep2}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            >
              Далее
              <ChevronRight className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="max-w-2xl space-y-5 rounded-xl border border-slate-700 bg-slate-900/50 p-6">
          <h2 className="text-lg font-medium text-white">Данные для документа</h2>
          <ValidatedControl label="Дата заседания (необязательно)" htmlFor="meeting-date" error={fieldErrors.meetingDate}>
            <input
              id="meeting-date"
              type="text"
              inputMode="numeric"
              placeholder="ГГГГ-ММ-ДД"
              value={meetingDate}
              onChange={(e) => setMeetingDate(e.target.value)}
              aria-invalid={!!fieldErrors.meetingDate}
              aria-describedby={fieldErrors.meetingDate ? "meeting-date-err-tip" : undefined}
              title={fieldErrors.meetingDate || undefined}
              className={`${inputBase} ${fieldErrors.meetingDate ? ringError : ""}`}
            />
          </ValidatedControl>
          <ValidatedControl label="Повестка / формулировка вопроса" htmlFor="agenda" error={fieldErrors.agenda}>
            <textarea
              id="agenda"
              rows={4}
              value={agenda}
              onChange={(e) => setAgenda(e.target.value)}
              aria-invalid={!!fieldErrors.agenda}
              aria-describedby={fieldErrors.agenda ? "agenda-err-tip" : undefined}
              title={fieldErrors.agenda || undefined}
              placeholder="Например: избрание генерального директора, изменение состава органов управления..."
              className={`${inputBase} min-h-[6rem] ${fieldErrors.agenda ? ringError : ""}`}
            />
          </ValidatedControl>
          <ValidatedControl label="Участники (ФИО, по одному на строку)" htmlFor="attendees" error={fieldErrors.attendeesText}>
            <textarea
              id="attendees"
              rows={5}
              value={attendeesText}
              onChange={(e) => setAttendeesText(e.target.value)}
              aria-invalid={!!fieldErrors.attendeesText}
              aria-describedby={fieldErrors.attendeesText ? "attendees-err-tip" : undefined}
              title={fieldErrors.attendeesText || undefined}
              placeholder={`Иванов Иван Иванович\nПетрова Мария Сергеевна`}
              className={`${inputBase} min-h-[7rem] font-mono ${fieldErrors.attendeesText ? ringError : ""}`}
            />
          </ValidatedControl>

          <div className="flex flex-wrap justify-between gap-2">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden />
              Назад
            </button>
            <button
              type="button"
              onClick={goStep3}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            >
              Далее к генерации
              <ChevronRight className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4 rounded-xl border border-slate-700 bg-slate-900/50 p-6">
          <h2 className="text-lg font-medium text-white">Генерация и правка текста</h2>

          {genLoading ? (
            <div className="flex flex-col items-center justify-center gap-5 py-20">
              <div
                className="h-16 w-16 rounded-full border-[5px] border-emerald-500/25 border-t-emerald-400 shadow-[0_0_24px_rgba(52,211,153,0.25)] animate-spin"
                aria-hidden
              />
              <p className="max-w-lg text-center text-base leading-relaxed text-emerald-100/95">
                ИИ-юрист изучает законодательство и Устав…
              </p>
              <p className="text-sm text-slate-500">Обычно это занимает от нескольких секунд до минуты.</p>
            </div>
          ) : (
            <>
              {genError ? (
                <div className="flex items-start gap-2 rounded-lg border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-100">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                  <div>
                    <div className="font-medium">Не удалось сгенерировать</div>
                    <div>{genError}</div>
                    <button
                      type="button"
                      className="mt-2 rounded border border-red-700 px-3 py-1 text-xs hover:bg-red-900/60"
                      onClick={() => {
                        setGenTrigger((n) => n + 1);
                      }}
                    >
                      Повторить запрос
                    </button>
                  </div>
                </div>
              ) : null}

              {!genError && (
                <>
                  <div className="grid gap-4 lg:grid-cols-2 lg:gap-6">
                    <div className="flex min-h-[22rem] flex-col gap-2">
                      <span className="text-xs uppercase tracking-wide text-slate-500">Редактор (Markdown)</span>
                      <textarea
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                        className={`${inputBase} min-h-[20rem] flex-1 font-mono text-xs leading-relaxed`}
                        spellCheck={false}
                        aria-label="Текст документа в формате Markdown"
                      />
                    </div>
                    <div className="flex min-h-[22rem] flex-col gap-2">
                      <span className="text-xs uppercase tracking-wide text-slate-500">Предпросмотр</span>
                      <div className="min-h-0 flex-1 overflow-y-auto rounded-lg border border-slate-700 bg-slate-950/50 p-3 text-sm text-slate-200 [&_h1]:mb-2 [&_h1]:text-lg [&_h2]:mt-4 [&_h2]:text-base [&_li]:my-0.5 [&_p]:my-2 [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5">
                        <ReactMarkdown>{content || "_Пусто_"}</ReactMarkdown>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => setStep(2)}
                      className="inline-flex items-center gap-2 rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
                    >
                      <ChevronLeft className="h-4 w-4" aria-hidden />
                      Назад к данным
                    </button>
                    <div className="flex flex-wrap items-center gap-2">
                      {saveStatus ? (
                        <span className={`text-sm ${saveStatus.includes("Изменения") ? "text-emerald-400" : "text-red-300"}`}>
                          {saveStatus}
                        </span>
                      ) : null}
                      <button
                        type="button"
                        disabled={saving || !documentId}
                        onClick={saveEdits}
                        className={BTN_SAVE}
                      >
                        {saving ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                            Сохранение…
                          </>
                        ) : (
                          <>
                            <Save className="h-4 w-4" aria-hidden />
                            Сохранить правки
                          </>
                        )}
                      </button>
                      <Link
                        to="/compliance"
                        className="inline-flex items-center gap-2 rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
                      >
                        <Sparkles className="h-4 w-4 text-amber-300" aria-hidden />
                        На дашборд
                      </Link>
                    </div>
                  </div>
                </>
              )}

              {!genLoading && genError ? (
                <div className="pt-4">
                  <button
                    type="button"
                    onClick={() => setStep(2)}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
                  >
                    <ChevronLeft className="h-4 w-4" aria-hidden />
                    Назад к данным
                  </button>
                </div>
              ) : null}
            </>
          )}
        </div>
      )}
    </div>
  );
}
