import { useCallback, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import api from "../../api/client.js";
import { useAuthStore } from "../../store/authStore.js";

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

function sortOptionsByScore(options) {
  return [...(options || [])].sort((a, b) => a.score - b.score || String(a.id).localeCompare(String(b.id)));
}

/** Круговой зелёный спиннер (тусклое кольцо + яркая дуга сверху при вращении). */
function GreenRingSpinner({ sizeClass = "h-9 w-9", isPublic = false }) {
  const ring = isPublic
    ? "border-2 border-solid border-emerald-200 border-t-emerald-600"
    : "border-2 border-solid border-emerald-500/30 border-t-emerald-400";
  return (
    <div className={`${sizeClass} shrink-0 animate-spin rounded-full ${ring}`} aria-hidden />
  );
}

const verdictMdComponents = {
  p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  h1: ({ children }) => <h3 className="mb-2 mt-4 text-base font-bold text-slate-900 first:mt-0">{children}</h3>,
  h2: ({ children }) => <h3 className="mb-2 mt-4 text-base font-bold text-slate-900 first:mt-0">{children}</h3>,
  h3: ({ children }) => <h4 className="mb-2 mt-3 text-sm font-semibold text-slate-900 first:mt-0">{children}</h4>,
  code: ({ children }) => (
    <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em] text-teal-900">{children}</code>
  ),
  pre: ({ children }) => (
    <pre className="mb-3 overflow-x-auto rounded-lg bg-slate-100 p-3 text-xs text-slate-800 last:mb-0">{children}</pre>
  ),
  a: ({ href, children }) => (
    <a href={href} className="font-medium text-teal-700 underline decoration-teal-300 hover:text-teal-800" target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

const verdictMdComponentsDark = {
  ...verdictMdComponents,
  p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed text-slate-200">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
  li: ({ children }) => <li className="leading-relaxed text-slate-200">{children}</li>,
  h1: ({ children }) => <h3 className="mb-2 mt-4 text-base font-bold text-white first:mt-0">{children}</h3>,
  h2: ({ children }) => <h3 className="mb-2 mt-4 text-base font-bold text-white first:mt-0">{children}</h3>,
  h3: ({ children }) => <h4 className="mb-2 mt-3 text-sm font-semibold text-slate-100 first:mt-0">{children}</h4>,
  code: ({ children }) => (
    <code className="rounded bg-slate-800 px-1 py-0.5 font-mono text-[0.85em] text-teal-200">{children}</code>
  ),
  pre: ({ children }) => (
    <pre className="mb-3 overflow-x-auto rounded-lg bg-slate-950/80 p-3 text-xs text-slate-200 last:mb-0">{children}</pre>
  ),
  a: ({ href, children }) => (
    <a href={href} className="font-medium text-teal-300 underline hover:text-teal-200" target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

async function postAssessStream(questionnaireId, payload, { onDelta, onDone, onError }) {
  const token = useAuthStore.getState().token;
  const res = await fetch(`/api/questionnaires/${questionnaireId}/assess-stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      if (typeof j?.detail === "string") msg = j.detail;
    } catch {
      /* ignore */
    }
    onError(msg);
    return;
  }
  const reader = res.body?.getReader();
  if (!reader) {
    onError("Нет тела ответа");
    return;
  }
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const block of parts) {
        for (const line of block.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6).trim();
          if (data === "[DONE]") {
            onDone();
            return;
          }
          try {
            const j = JSON.parse(data);
            if (j.error) {
              onError(typeof j.error === "string" ? j.error : JSON.stringify(j.error));
              return;
            }
            if (typeof j.t === "string" && j.t) onDelta(j.t);
          } catch {
            /* ignore malformed chunk */
          }
        }
      }
    }
    onDone();
  } catch (e) {
    onError(e?.message ?? String(e));
  }
}

/**
 * Загрузка опросника, форма ответов, SSE assess-stream, вывод вердикта ИИ.
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
  const [streamActive, setStreamActive] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [pdfBusy, setPdfBusy] = useState(false);

  const ordered = useMemo(() => sortQuestions(qn?.questions), [qn]);
  const isPublic = variant === "public";

  const load = useCallback(async () => {
    if (!questionnaireId) return;
    setLoading(true);
    setLoadError("");
    setPhase("form");
    setAnalysis("");
    setStreamActive(false);
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

  /** Сообщение об ошибке, если не на все вопросы дан ответ; иначе пустая строка. */
  const validateAllAnswered = () => {
    for (const q of ordered) {
      const v = values[q.id] || { optionIds: [], text: "" };
      const shortQ = q.text.length > 120 ? `${q.text.slice(0, 120)}…` : q.text;
      if (q.type === "text") {
        if (!(v.text || "").trim()) {
          return `Ответьте на вопрос: ${shortQ}`;
        }
      } else if (q.type === "single") {
        if ((v.optionIds || []).length !== 1) {
          return `Выберите один вариант ответа: ${shortQ}`;
        }
      } else if (q.type === "multiple") {
        if (!(v.optionIds || []).length) {
          return `Выберите хотя бы один вариант: ${shortQ}`;
        }
      }
    }
    return "";
  };

  const onSubmit = async (ev) => {
    ev.preventDefault();
    setSubmitError("");
    if (!ordered.length) {
      setSubmitError("В опроснике нет вопросов.");
      return;
    }
    const validationError = validateAllAnswered();
    if (validationError) {
      setSubmitError(validationError);
      return;
    }
    setPhase("result");
    setAnalysis("");
    setStreamActive(true);
    try {
      await postAssessStream(questionnaireId, buildPayload(), {
        onDelta: (t) => setAnalysis((prev) => prev + t),
        onDone: () => setStreamActive(false),
        onError: (msg) => {
          setStreamActive(false);
          setSubmitError(msg || "Ошибка оценки");
          setPhase("form");
        },
      });
    } catch (e) {
      console.error(e);
      setStreamActive(false);
      setSubmitError(formatApiDetail(e) || "Ошибка оценки");
      setPhase("form");
    }
  };

  const shell = isPublic
    ? "mx-auto max-w-2xl rounded-2xl border border-teal-100/90 bg-white p-6 shadow-lg shadow-teal-900/5"
    : "rounded-xl border border-slate-800 bg-slate-900/60 p-6";

  const titleClass = isPublic ? "text-lg font-semibold text-slate-900" : "text-lg font-semibold text-white";
  const qTextClass = isPublic ? "text-sm font-medium text-slate-800" : "text-sm font-medium text-slate-200";
  const rangeClass = isPublic ? "mt-1 text-xs text-slate-500" : "mt-1 text-xs text-slate-500";
  const optionRowClass = isPublic
    ? "mt-2 flex cursor-pointer items-center gap-2 rounded-xl border border-transparent px-2 py-2 hover:border-teal-100 hover:bg-teal-50/50"
    : "mt-2 flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-800/60";
  const optionTextClass = isPublic ? "text-sm text-slate-700" : "text-sm text-slate-300";
  const optionScoreClass = isPublic ? "text-slate-500" : "text-slate-500";
  const inputTextareaClass = isPublic
    ? "mt-3 w-full rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500/30"
    : "mt-3 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-emerald-600 focus:outline-none";
  const dividerClass = isPublic ? "border-b border-slate-100 pb-5 last:border-0" : "border-b border-slate-800 pb-5 last:border-0";
  const verdictBoxClass = isPublic
    ? "rounded-xl border border-teal-100 bg-gradient-to-b from-teal-50/40 to-white p-4 text-sm text-slate-800"
    : "rounded-lg bg-slate-950/80 p-4 text-sm leading-relaxed text-slate-200";
  const mdComponents = isPublic ? verdictMdComponents : verdictMdComponentsDark;
  const primaryBtnClass = isPublic
    ? "rounded-xl bg-teal-600 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-teal-500 sm:w-auto sm:px-8"
    : "rounded-lg bg-emerald-600 py-2.5 text-sm font-medium text-white hover:bg-emerald-500 sm:w-auto sm:px-8";
  const secondaryBtnClass = isPublic
    ? "rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
    : "rounded-lg border border-slate-500 bg-slate-800 px-4 py-2 text-sm font-medium text-slate-100 hover:bg-slate-700 disabled:opacity-50";
  const closeBtnClass = isPublic
    ? "shrink-0 rounded-lg px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 hover:text-slate-800"
    : "shrink-0 rounded-lg px-2 py-1 text-sm text-slate-400 hover:bg-slate-800 hover:text-white";

  if (loading) {
    return (
      <div className={shell}>
        <p className={isPublic ? "text-sm text-slate-600" : "text-sm text-slate-400"}>Загрузка опросника…</p>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className={shell}>
        <p className={isPublic ? "text-sm text-red-600" : "text-sm text-red-400"}>{loadError}</p>
        {onClose ? (
          <button type="button" className={`mt-4 ${primaryBtnClass} px-3 py-1.5`} onClick={onClose}>
            Закрыть
          </button>
        ) : null}
      </div>
    );
  }

  const showVerdict = phase === "result";

  return (
    <div className={shell}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className={titleClass}>{qn?.title}</h2>
        </div>
        {onClose ? (
          <button type="button" className={closeBtnClass} onClick={onClose} aria-label="Закрыть">
            ✕
          </button>
        ) : null}
      </div>

      {showVerdict ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className={isPublic ? "text-sm font-semibold text-teal-800" : "text-sm font-medium text-emerald-400"}>
              Заключение
            </h3>
            {streamActive ? (
              <span
                className={`inline-flex items-center gap-2.5 rounded-full py-1 pl-1 pr-3 text-xs font-medium ${
                  isPublic
                    ? "bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200/80"
                    : "bg-emerald-950/50 text-emerald-300 ring-1 ring-emerald-500/25"
                }`}
                role="status"
                aria-live="polite"
              >
                <GreenRingSpinner sizeClass="h-7 w-7" isPublic={isPublic} />
                Формирование ответа
              </span>
            ) : null}
          </div>
          <div className={verdictBoxClass}>
            {analysis.trim() ? (
              <ReactMarkdown components={mdComponents}>{analysis}</ReactMarkdown>
            ) : streamActive ? (
              <div
                className={`flex flex-col items-center justify-center gap-4 py-10 ${
                  isPublic ? "text-emerald-800" : "text-emerald-300"
                }`}
                role="status"
                aria-live="polite"
              >
                <GreenRingSpinner sizeClass="h-12 w-12" isPublic={isPublic} />
                <p className="text-sm font-medium">Формирование ответа</p>
              </div>
            ) : (
              <p className={isPublic ? "text-slate-500" : "text-slate-400"}>Пустой ответ модели.</p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={primaryBtnClass}
              disabled={streamActive}
              onClick={() => {
                setPhase("form");
                setAnalysis("");
                setStreamActive(false);
                load();
              }}
            >
              Пройти снова
            </button>
            <button
              type="button"
              disabled={pdfBusy || !analysis.trim() || streamActive}
              className={secondaryBtnClass}
              onClick={async () => {
                setPdfBusy(true);
                try {
                  const res = await api.post(
                    "/questionnaires/verdict-pdf",
                    { title: (qn?.title || "").trim(), analysis },
                    { responseType: "blob" },
                  );
                  const blob = new Blob([res.data], { type: "application/pdf" });
                  const url = URL.createObjectURL(blob);
                  const cd = res.headers["content-disposition"] || res.headers["Content-Disposition"];
                  let fname = "verdikt-ii.pdf";
                  if (typeof cd === "string") {
                    const m = cd.match(/filename="([^"]+)"/i) || cd.match(/filename=([^;]+)/i);
                    if (m) fname = m[1].trim();
                  }
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = fname;
                  a.rel = "noopener";
                  document.body.appendChild(a);
                  a.click();
                  a.remove();
                  URL.revokeObjectURL(url);
                } catch (e) {
                  console.error(e);
                  let msg = "";
                  if (e?.response?.data instanceof Blob) {
                    try {
                      const t = await e.response.data.text();
                      const j = JSON.parse(t);
                      msg = typeof j?.detail === "string" ? j.detail : t;
                    } catch {
                      msg = "Ошибка сервера при формировании PDF";
                    }
                  } else {
                    msg = formatApiDetail(e);
                  }
                  window.alert(msg || "Не удалось скачать PDF.");
                } finally {
                  setPdfBusy(false);
                }
              }}
            >
              {pdfBusy ? "PDF…" : "Скачать PDF"}
            </button>
            {onClose ? (
              <button type="button" className={secondaryBtnClass} onClick={onClose}>
                Закрыть
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {phase === "form" ? (
        <form onSubmit={onSubmit} className="space-y-6">
          {!ordered.length ? (
            <p className={isPublic ? "text-sm text-amber-700" : "text-sm text-amber-400"}>
              В этом опроснике пока нет вопросов.
            </p>
          ) : null}
          {ordered.map((q) => {
            const opts = sortOptionsByScore(q.options);
            return (
              <div key={q.id} className={dividerClass}>
                <p className={qTextClass}>{q.text}</p>
                {!isPublic ? (
                  <p className={rangeClass}>
                    Диапазон баллов: {q.min_score} — {q.max_score}
                  </p>
                ) : null}
                {q.type === "text" ? (
                  <textarea
                    className={inputTextareaClass}
                    rows={4}
                    placeholder="Ваш ответ"
                    value={values[q.id]?.text ?? ""}
                    onChange={(e) => setText(q.id, e.target.value)}
                  />
                ) : null}
                {q.type === "single"
                  ? opts.map((o) => (
                      <label key={o.id} className={optionRowClass}>
                        <input
                          type="radio"
                          name={`q-${q.id}`}
                          className={isPublic ? "text-teal-600 focus:ring-teal-500" : "text-emerald-500 focus:ring-emerald-500"}
                          checked={(values[q.id]?.optionIds || []).includes(o.id)}
                          onChange={() => setOptionSingle(q.id, o.id)}
                        />
                        <span className={optionTextClass}>
                          {o.text}
                          {!isPublic ? (
                            <>
                              {" "}
                              <span className={optionScoreClass}>({o.score} б.)</span>
                            </>
                          ) : null}
                        </span>
                      </label>
                    ))
                  : null}
                {q.type === "multiple"
                  ? opts.map((o) => (
                      <label key={o.id} className={optionRowClass}>
                        <input
                          type="checkbox"
                          className={
                            isPublic
                              ? "rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                              : "rounded border-slate-600 text-emerald-500 focus:ring-emerald-500"
                          }
                          checked={(values[q.id]?.optionIds || []).includes(o.id)}
                          onChange={() => toggleOptionMultiple(q.id, o.id)}
                        />
                        <span className={optionTextClass}>
                          {o.text}
                          {!isPublic ? (
                            <>
                              {" "}
                              <span className={optionScoreClass}>({o.score} б.)</span>
                            </>
                          ) : null}
                        </span>
                      </label>
                    ))
                  : null}
              </div>
            );
          })}
          {submitError ? (
            <p className={isPublic ? "text-sm text-red-600" : "text-sm text-red-400"}>{submitError}</p>
          ) : null}
          {ordered.length > 0 ? (
            <button type="submit" className={`w-full ${primaryBtnClass}`}>
              Отправить на оценку
            </button>
          ) : null}
        </form>
      ) : null}
    </div>
  );
}
