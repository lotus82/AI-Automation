import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

function formatApiDetail(data) {
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map((x) => x?.msg ?? x).join("; ");
  if (data?.detail != null) return JSON.stringify(data.detail);
  return "Ошибка отправки";
}

export function PublicRegistrationPage() {
  const { eventId } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);
  const [answers, setAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const load = useCallback(async () => {
    if (!eventId) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/forms/public/events/${eventId}`);
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j?.detail ?? `HTTP ${res.status}`);
      }
      const data = await res.json();
      setPayload(data);
    } catch (e) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    load();
  }, [load]);

  const sortedFields = useMemo(() => {
    const f = payload?.fields ?? [];
    return [...f].sort((a, b) => (a.order ?? 0) - (b.order ?? 0) || String(a.id).localeCompare(String(b.id)));
  }, [payload]);

  const setAnswer = (id, v) => {
    setAnswers((prev) => ({ ...prev, [id]: v }));
  };

  const toggleMulti = (id, option, checked) => {
    setAnswers((prev) => {
      const cur = Array.isArray(prev[id]) ? [...prev[id]] : [];
      if (checked) {
        if (!cur.includes(option)) cur.push(option);
      } else {
        const i = cur.indexOf(option);
        if (i >= 0) cur.splice(i, 1);
      }
      return { ...prev, [id]: cur };
    });
  };

  const clearForm = () => {
    setAnswers({});
    setSubmitError("");
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!payload?.registration_open) return;
    setSubmitting(true);
    setSubmitError("");
    try {
      const res = await fetch(`/api/forms/public/events/${eventId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ answers }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(formatApiDetail(data) || `HTTP ${res.status}`);
      }
      setDone(true);
    } catch (err) {
      setSubmitError(err?.message ?? String(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (!eventId) {
    return (
      <div className="min-h-screen bg-slate-950 p-6 text-center text-sm text-red-400">Некорректная ссылка.</div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-12 text-center text-slate-400">Загрузка формы…</div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-12 text-center text-sm text-red-400">{error}</div>
    );
  }

  if (done) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-12">
        <div className="mx-auto max-w-lg rounded-2xl border border-emerald-800/50 bg-slate-900/80 p-8 text-center text-slate-100 shadow-xl">
          <p className="text-lg font-semibold text-emerald-300">Спасибо!</p>
          <p className="mt-2 text-sm text-slate-400">Ваша заявка отправлена.</p>
        </div>
      </div>
    );
  }

  const closed = !payload.registration_open;

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
      <div className="mx-auto max-w-lg">
        <header className="rounded-2xl border border-slate-600/70 border-t-4 border-t-emerald-500/90 bg-gradient-to-b from-emerald-950/40 to-slate-900/80 px-5 py-5 shadow-lg shadow-black/20">
          <h1 className="text-2xl font-bold text-white">{payload.event_title}</h1>
          <p className="mt-2 text-sm font-medium text-emerald-200/90">
            {payload.event_start_date} — {payload.event_end_date}
          </p>
        </header>

        {closed ? (
          <p className="mt-6 rounded-xl border border-slate-700 bg-slate-900/60 px-4 py-6 text-center text-slate-300">
            {payload.closed_message ?? "Регистрация завершена."}
          </p>
        ) : (
          <form className="mt-6 space-y-4" onSubmit={onSubmit}>
            {sortedFields.map((field) => (
              <div
                key={field.id}
                className="rounded-xl border border-slate-600/80 bg-slate-900/55 px-4 py-4 shadow-sm sm:px-5 sm:py-5"
              >
                <label className="mb-2 block text-sm font-medium text-slate-200" htmlFor={`fld-${field.id}`}>
                  {field.label}
                  {field.required ? <span className="text-red-400"> *</span> : null}
                </label>
                {field.type === "long_text" ? (
                  <textarea
                    id={`fld-${field.id}`}
                    className="w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                    rows={3}
                    required={field.required}
                    placeholder={field.placeholder ?? ""}
                    value={answers[field.id] ?? ""}
                    onChange={(e) => setAnswer(field.id, e.target.value)}
                  />
                ) : null}
                {field.type === "short_text" || field.type === "phone" || field.type === "email" ? (
                  <input
                    id={`fld-${field.id}`}
                    type={field.type === "email" ? "email" : "text"}
                    className="w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                    required={field.required}
                    placeholder={field.placeholder ?? ""}
                    value={answers[field.id] ?? ""}
                    onChange={(e) => setAnswer(field.id, e.target.value)}
                  />
                ) : null}
                {field.type === "number" ? (
                  <input
                    id={`fld-${field.id}`}
                    type="number"
                    step="any"
                    className="w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                    required={field.required}
                    value={answers[field.id] ?? ""}
                    onChange={(e) => setAnswer(field.id, e.target.value)}
                  />
                ) : null}
                {field.type === "date" ? (
                  <input
                    id={`fld-${field.id}`}
                    type="date"
                    className="w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                    required={field.required}
                    value={answers[field.id] ?? ""}
                    onChange={(e) => setAnswer(field.id, e.target.value)}
                  />
                ) : null}
                {field.type === "single_choice" ? (
                  <div className="space-y-2">
                    {(field.options ?? []).map((opt) => (
                      <label key={opt} className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
                        <input
                          type="radio"
                          name={`fld-${field.id}`}
                          className="h-4 w-4 border-slate-500 bg-slate-900 accent-emerald-500"
                          required={field.required}
                          checked={answers[field.id] === opt}
                          onChange={() => setAnswer(field.id, opt)}
                        />
                        {opt}
                      </label>
                    ))}
                  </div>
                ) : null}
                {field.type === "multiple_choice" ? (
                  <div className="space-y-2">
                    {(field.options ?? []).map((opt) => {
                      const cur = Array.isArray(answers[field.id]) ? answers[field.id] : [];
                      return (
                        <label key={opt} className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-slate-500 bg-slate-900 accent-emerald-500"
                            checked={cur.includes(opt)}
                            onChange={(e) => toggleMulti(field.id, opt, e.target.checked)}
                          />
                          {opt}
                        </label>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            ))}

            {submitError ? <p className="text-sm text-red-400">{submitError}</p> : null}

            <div className="flex flex-col gap-3 pt-2 sm:flex-row sm:items-stretch">
              <button
                type="submit"
                disabled={submitting}
                className="min-h-[2.75rem] flex-1 rounded-lg bg-emerald-600 py-3 text-sm font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-50"
              >
                {submitting ? "Отправка…" : "Отправить"}
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={clearForm}
                className="min-h-[2.75rem] rounded-lg border border-slate-500 bg-slate-800/80 px-4 py-3 text-sm font-medium text-slate-200 hover:bg-slate-800 disabled:opacity-50 sm:w-auto sm:shrink-0"
              >
                Очистить форму
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
