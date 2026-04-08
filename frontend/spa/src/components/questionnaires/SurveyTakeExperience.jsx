import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../../api/client.js";

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

function sortQuestions(qs) {
  return [...(qs || [])].sort((a, b) => a.order - b.order || String(a.id).localeCompare(String(b.id)));
}

/**
 * Загрузка опросника, форма ответов, POST assess, вывод вердикта ИИ.
 * @param {{ questionnaireId: string, onClose?: () => void, variant?: 'panel' | 'public' }} props
 */
export function SurveyTakeExperience({ questionnaireId, onClose, variant = "panel" }) {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [qn, setQn] = useState(null);
  /** @type {Record<string, { optionIds: string[], text: string }>} */
  const [values, setValues] = useState({});
  const [phase, setPhase] = useState("form");
  const [analysis, setAnalysis] = useState("");
  const [submitError, setSubmitError] = useState("");

  const ordered = useMemo(() => sortQuestions(qn?.questions), [qn]);

  const load = useCallback(async () => {
    if (!questionnaireId) return;
    setLoading(true);
    setLoadError("");
    setPhase("form");
    setAnalysis("");
    setSubmitError("");
    setValues({});
    try {
      const { data } = await api.get(`/questionnaires/${questionnaireId}`);
      setQn(data);
      const init = {};
      for (const q of sortQuestions(data?.questions)) {
        init[q.id] =
          q.type === "text" ? { optionIds: [], text: "" } : { optionIds: [], text: "" };
      }
      setValues(init);
    } catch (e) {
      console.error(e);
      setLoadError(formatApiDetail(e) || "Не удалось загрузить опросник");
      setQn(null);
    } finally {
      setLoading(false);
    }
  }, [questionnaireId]);

  useEffect(() => {
    load();
  }, [load]);

  const setOptionSingle = (qid, optId) => {
    setValues((prev) => ({
      ...prev,
      [qid]: { ...prev[qid], optionIds: [optId] },
    }));
  };

  const toggleOptionMultiple = (qid, optId) => {
    setValues((prev) => {
      const cur = prev[qid]?.optionIds || [];
      const has = cur.includes(optId);
      const next = has ? cur.filter((x) => x !== optId) : [...cur, optId];
      return { ...prev, [qid]: { ...prev[qid], optionIds: next } };
    });
  };

  const setText = (qid, text) => {
    setValues((prev) => ({
      ...prev,
      [qid]: { ...prev[qid], text },
    }));
  };

  const buildPayload = () => {
    const answers = ordered.map((q) => {
      const v = values[q.id] || { optionIds: [], text: "" };
      if (q.type === "text") {
        return {
          question_id: q.id,
          option_ids: [],
          text_answer: (v.text || "").trim() || null,
        };
      }
      return {
        question_id: q.id,
        option_ids: v.optionIds || [],
        text_answer: null,
      };
    });
    return { answers };
  };

  const onSubmit = async (ev) => {
    ev.preventDefault();
    setSubmitError("");
    if (!ordered.length) {
      setSubmitError("В опроснике нет вопросов.");
      return;
    }
    setPhase("loading");
    try {
      const { data } = await api.post(
        `/questionnaires/${questionnaireId}/assess`,
        buildPayload(),
      );
      setAnalysis((data?.analysis || "").trim() || "Пустой ответ модели.");
      setPhase("result");
    } catch (e) {
      console.error(e);
      setSubmitError(formatApiDetail(e) || "Ошибка оценки");
      setPhase("form");
    }
  };

  const shell =
    variant === "public"
      ? "mx-auto max-w-2xl rounded-xl border border-slate-800 bg-slate-900/90 p-6 shadow-xl"
      : "rounded-xl border border-slate-800 bg-slate-900/60 p-6";

  if (loading) {
    return (
      <div className={shell}>
        <p className="text-sm text-slate-400">Загрузка опросника…</p>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className={shell}>
        <p className="text-sm text-red-400">{loadError}</p>
        {onClose ? (
          <button
            type="button"
            className="mt-4 rounded-lg bg-slate-700 px-3 py-1.5 text-sm text-white hover:bg-slate-600"
            onClick={onClose}
          >
            Закрыть
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className={shell}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-white">{qn?.title}</h2>
          {variant === "public" ? (
            <p className="mt-1 text-xs text-slate-500">Внешняя ссылка на опрос</p>
          ) : null}
        </div>
        {onClose ? (
          <button
            type="button"
            className="shrink-0 rounded-lg px-2 py-1 text-sm text-slate-400 hover:bg-slate-800 hover:text-white"
            onClick={onClose}
            aria-label="Закрыть"
          >
            ✕
          </button>
        ) : null}
      </div>

      {phase === "loading" ? (
        <div className="flex flex-col items-center gap-3 py-12">
          <div
            className="h-10 w-10 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400"
            aria-hidden
          />
          <p className="text-sm text-slate-400">ИИ анализирует ответы…</p>
        </div>
      ) : null}

      {phase === "result" ? (
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-emerald-400">Вердикт ИИ</h3>
          <div className="whitespace-pre-wrap rounded-lg bg-slate-950/80 p-4 text-sm leading-relaxed text-slate-200">
            {analysis}
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
              onClick={() => {
                setPhase("form");
                setAnalysis("");
                load();
              }}
            >
              Пройти снова
            </button>
            {onClose ? (
              <button
                type="button"
                className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
                onClick={onClose}
              >
                Закрыть
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {phase === "form" ? (
        <form onSubmit={onSubmit} className="space-y-6">
          {!ordered.length ? (
            <p className="text-sm text-amber-400">В этом опроснике пока нет вопросов.</p>
          ) : null}
          {ordered.map((q) => (
            <div key={q.id} className="border-b border-slate-800 pb-5 last:border-0">
              <p className="text-sm font-medium text-slate-200">{q.text}</p>
              <p className="mt-1 text-xs text-slate-500">
                Диапазон баллов: {q.min_score} — {q.max_score}
              </p>
              {q.type === "text" ? (
                <textarea
                  className="mt-3 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-emerald-600 focus:outline-none"
                  rows={4}
                  placeholder="Ваш ответ"
                  value={values[q.id]?.text ?? ""}
                  onChange={(e) => setText(q.id, e.target.value)}
                />
              ) : null}
              {q.type === "single"
                ? (q.options || []).map((o) => (
                    <label
                      key={o.id}
                      className="mt-2 flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-800/60"
                    >
                      <input
                        type="radio"
                        name={`q-${q.id}`}
                        className="text-emerald-500 focus:ring-emerald-500"
                        checked={(values[q.id]?.optionIds || []).includes(o.id)}
                        onChange={() => setOptionSingle(q.id, o.id)}
                      />
                      <span className="text-sm text-slate-300">
                        {o.text}{" "}
                        <span className="text-slate-500">({o.score} б.)</span>
                      </span>
                    </label>
                  ))
                : null}
              {q.type === "multiple"
                ? (q.options || []).map((o) => (
                    <label
                      key={o.id}
                      className="mt-2 flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-800/60"
                    >
                      <input
                        type="checkbox"
                        className="rounded border-slate-600 text-emerald-500 focus:ring-emerald-500"
                        checked={(values[q.id]?.optionIds || []).includes(o.id)}
                        onChange={() => toggleOptionMultiple(q.id, o.id)}
                      />
                      <span className="text-sm text-slate-300">
                        {o.text}{" "}
                        <span className="text-slate-500">({o.score} б.)</span>
                      </span>
                    </label>
                  ))
                : null}
            </div>
          ))}
          {submitError ? <p className="text-sm text-red-400">{submitError}</p> : null}
          {ordered.length > 0 ? (
            <button
              type="submit"
              className="w-full rounded-lg bg-emerald-600 py-2.5 text-sm font-medium text-white hover:bg-emerald-500 sm:w-auto sm:px-8"
            >
              Отправить на оценку ИИ
            </button>
          ) : null}
        </form>
      ) : null}
    </div>
  );
}
