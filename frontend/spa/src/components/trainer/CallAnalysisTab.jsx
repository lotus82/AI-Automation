import { useCallback, useEffect, useState } from "react";
import api from "../../api/client.js";

function formatErr(err) {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (d != null) return JSON.stringify(d);
  return err?.message ?? String(err);
}

const inputClass =
  "w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500";
const labelClass = "mb-1 block text-sm font-medium text-slate-200";

/**
 * BANT/MEDDIC по транскрипту (раньше вкладка «Аналитика звонков» в ИИ-тренере).
 */
export function CallAnalysisTab() {
  const [methodologies, setMethodologies] = useState([]);
  const [loadMetaErr, setLoadMetaErr] = useState(null);

  const [methodologyCode, setMethodologyCode] = useState("bant");
  const [transcript, setTranscript] = useState("");
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [analyzeErr, setAnalyzeErr] = useState(null);
  const [analyzeResult, setAnalyzeResult] = useState(null);

  const loadMethodologies = useCallback(async () => {
    setLoadMetaErr(null);
    try {
      const { data } = await api.get("/trainer/methodologies");
      setMethodologies(Array.isArray(data) ? data : []);
    } catch (e) {
      setLoadMetaErr(formatErr(e));
    }
  }, []);

  useEffect(() => {
    void loadMethodologies();
  }, [loadMethodologies]);

  useEffect(() => {
    if (methodologies.length) {
      const codes = methodologies.map((x) => x.code);
      if (!codes.includes(methodologyCode)) {
        setMethodologyCode(codes[0] || "bant");
      }
    }
  }, [methodologies, methodologyCode]);

  const onAnalyze = async (e) => {
    e.preventDefault();
    setAnalyzeLoading(true);
    setAnalyzeErr(null);
    setAnalyzeResult(null);
    try {
      const { data } = await api.post("/trainer/analyze", {
        transcript: transcript.trim(),
        methodology_code: methodologyCode,
      });
      setAnalyzeResult(data);
    } catch (err) {
      setAnalyzeErr(formatErr(err));
    } finally {
      setAnalyzeLoading(false);
    }
  };

  const bant = analyzeResult?.bant;
  const meddic = analyzeResult?.meddic;

  return (
    <div
      className="rounded-b-xl rounded-tr-xl border border-t-0 border-slate-600 bg-slate-800/30 p-5"
      role="tabpanel"
    >
      {loadMetaErr && (
        <p className="mb-4 rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">
          {loadMetaErr}
        </p>
      )}

      <form className="space-y-4" onSubmit={onAnalyze}>
        <div>
          <label className={labelClass} htmlFor="qa-trainer-method">
            Методика
          </label>
          <select
            id="qa-trainer-method"
            className={inputClass}
            value={methodologyCode}
            onChange={(e) => setMethodologyCode(e.target.value)}
          >
            {methodologies.length === 0 ? (
              <>
                <option value="bant">BANT</option>
                <option value="meddic">MEDDIC</option>
              </>
            ) : (
              methodologies.map((m) => (
                <option key={m.id} value={m.code}>
                  {m.name}
                </option>
              ))
            )}
          </select>
        </div>
        <div>
          <label className={labelClass} htmlFor="qa-trainer-transcript">
            Транскрипт диалога
          </label>
          <textarea
            id="qa-trainer-transcript"
            className={`${inputClass} min-h-[160px] resize-y`}
            placeholder="Вставьте текст транскрипта менеджера и клиента…"
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
          />
        </div>
        {analyzeErr && <p className="text-sm text-red-400">{analyzeErr}</p>}
        <button
          type="submit"
          className="rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          disabled={analyzeLoading || !transcript.trim()}
        >
          {analyzeLoading ? "Анализ…" : "Проанализировать"}
        </button>
      </form>

      {bant && (
        <div className="mt-8 space-y-3">
          <h3 className="text-lg font-semibold text-white">Результат BANT</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ["Budget", bant.budget],
              ["Authority", bant.authority],
              ["Need", bant.need],
              ["Timeline", bant.timeline],
            ].map(([title, val]) => (
              <div
                key={title}
                className="rounded-xl border border-slate-700 bg-slate-900/50 p-3 text-sm"
              >
                <div className="mb-1 text-xs font-semibold uppercase text-slate-500">{title}</div>
                <div className="text-slate-200">{val}</div>
              </div>
            ))}
          </div>
          <div className="rounded-xl border border-emerald-800/60 bg-emerald-950/25 p-4">
            <div className="mb-2 text-sm font-semibold text-emerald-300">Рекомендации ИИ</div>
            <p className="whitespace-pre-wrap text-sm text-slate-200">{bant.recommendation}</p>
          </div>
        </div>
      )}

      {meddic && (
        <div className="mt-8 space-y-3">
          <h3 className="text-lg font-semibold text-white">Результат MEDDIC</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ["Metrics", meddic.metrics],
              ["Economic buyer", meddic.economic_buyer],
              ["Decision criteria", meddic.decision_criteria],
              ["Decision process", meddic.decision_process],
              ["Identify pain", meddic.identify_pain],
              ["Champion", meddic.champion],
            ].map(([title, val]) => (
              <div
                key={title}
                className="rounded-xl border border-slate-700 bg-slate-900/50 p-3 text-sm"
              >
                <div className="mb-1 text-xs font-semibold uppercase text-slate-500">{title}</div>
                <div className="text-slate-200">{val}</div>
              </div>
            ))}
          </div>
          <div className="rounded-xl border border-emerald-800/60 bg-emerald-950/25 p-4">
            <div className="mb-2 text-sm font-semibold text-emerald-300">Рекомендации ИИ</div>
            <p className="whitespace-pre-wrap text-sm text-slate-200">{meddic.recommendation}</p>
          </div>
        </div>
      )}
    </div>
  );
}
