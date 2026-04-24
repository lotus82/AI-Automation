import { BarChart3 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../api/client.js";
import { IconDeleteButton } from "../components/ui/IconActionButtons.jsx";
import { ChatBotsMonitoring } from "../components/bots/ChatBotsMonitoring.jsx";
import { CallAnalysisTab } from "../components/trainer/CallAnalysisTab.jsx";
import { PAGE_H1, PAGE_HEADER, PAGE_INNER, PAGE_TEXT, PAGE_TITLE_ICON, TAB_ROW, tabBtn } from "../styles/pageLayout.js";
import { formatDateTimeRu } from "../utils/dateTimeFormat.js";

function snippet(text, maxLen) {
  if (!text) return "—";
  if (text.length <= maxLen) return text;
  return `${text.slice(0, maxLen)}…`;
}

function recordingUrl(callId) {
  return `/api/calls/${encodeURIComponent(callId)}/recording`;
}

/**
 * ИИ-контроль (QA): реестр звонков / ОКК, аналитика по методикам (BANT/MEDDIC), проверка API.
 */
export function QAPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const mainTab = useMemo(() => {
    const t = searchParams.get("tab");
    if (t === "analysis") return "analysis";
    if (t === "bots") return "bots";
    return "calls";
  }, [searchParams]);

  const setMainTab = (next) => {
    if (next === "analysis") {
      setSearchParams({ tab: "analysis" }, { replace: true });
    } else if (next === "bots") {
      setSearchParams({ tab: "bots" }, { replace: true });
    } else {
      setSearchParams({}, { replace: true });
    }
  };

  const [apiStatus, setApiStatus] = useState("idle");
  const [apiHint, setApiHint] = useState(null);

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [transcriptRec, setTranscriptRec] = useState(null);

  const loadCalls = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const { data } = await api.get("/calls");
      setItems(Array.isArray(data?.items) ? data.items : []);
    } catch (e) {
      const msg =
        e?.response?.data?.detail != null
          ? String(e.response.data.detail)
          : e?.message ?? String(e);
      setLoadError(msg);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCalls();
  }, [loadCalls]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setApiStatus("loading");
      try {
        const { data } = await api.get("/health");
        if (!cancelled) {
          setApiHint(typeof data === "object" ? JSON.stringify(data) : String(data));
          setApiStatus("ok");
        }
      } catch (e) {
        if (!cancelled) {
          setApiHint(e?.message || "Ошибка сети");
          setApiStatus("error");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!transcriptOpen) return;
    const onKey = (ev) => {
      if (ev.key === "Escape") {
        setTranscriptOpen(false);
        setTranscriptRec(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [transcriptOpen]);

  const openTranscript = (rec) => {
    setTranscriptRec(rec);
    setTranscriptOpen(true);
  };

  const closeTranscript = () => {
    setTranscriptOpen(false);
    setTranscriptRec(null);
  };

  const onDeleteRecording = async (e, callId) => {
    e.stopPropagation();
    if (!window.confirm("Удалить файл записи разговора? Строка в таблице останется.")) {
      return;
    }
    try {
      await api.delete(`/calls/${encodeURIComponent(callId)}/recording`);
      await loadCalls();
    } catch (err) {
      window.alert(
        `Не удалось удалить: ${err?.response?.data?.detail ?? err?.message ?? String(err)}`
      );
    }
  };

  const onDeleteCall = async (e, callId) => {
    e.stopPropagation();
    if (!window.confirm("Удалить этот диалог целиком из базы? Действие необратимо.")) {
      return;
    }
    try {
      await api.delete(`/calls/${encodeURIComponent(callId)}`);
      await loadCalls();
    } catch (err) {
      window.alert(
        `Не удалось удалить: ${err?.response?.data?.detail ?? err?.message ?? String(err)}`
      );
    }
  };

  const thClass =
    "px-2 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400";
  const tdClass = "px-2 py-2 align-top text-sm text-slate-200";
  const panelClass =
    "mb-6 rounded-xl border border-slate-700/80 bg-slate-800/40 p-4 text-slate-300";

  return (
    <div className={`${PAGE_INNER} ${PAGE_TEXT}`}>
      <header className={PAGE_HEADER}>
        <BarChart3 className={PAGE_TITLE_ICON} strokeWidth={1.5} aria-hidden />
        <h1 className={PAGE_H1}>ИИ-контроль (QA)</h1>
      </header>

      <div className={TAB_ROW} role="tablist" aria-label="Раздел ИИ-контроль">
        <button
          type="button"
          role="tab"
          aria-selected={mainTab === "calls"}
          className={tabBtn(mainTab === "calls")}
          onClick={() => setMainTab("calls")}
        >
          Звонки
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mainTab === "bots"}
          className={tabBtn(mainTab === "bots")}
          onClick={() => setMainTab("bots")}
        >
          Боты
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mainTab === "analysis"}
          className={tabBtn(mainTab === "analysis")}
          onClick={() => setMainTab("analysis")}
        >
          Аналитика звонков
        </button>
      </div>

      {mainTab === "analysis" && (
        <div className="mb-10 w-full min-w-0">
          <CallAnalysisTab />
        </div>
      )}

      {mainTab === "bots" && (
        <div className="mb-10">
          <ChatBotsMonitoring />
        </div>
      )}

      {mainTab === "calls" && (
        <>

      <div className="overflow-x-auto rounded-xl border border-slate-700/80 bg-slate-900/40">
        <table className="w-full min-w-[960px] border-collapse text-left">
          <thead>
            <tr className="border-b border-slate-600 bg-slate-900/60">
              
              <th className={thClass}>Направление</th>
              <th className={thClass}>Номер</th>
              <th className={thClass}>Статус</th>
              <th className={thClass}>Длительность (с)</th>
              <th className={thClass}>Создано</th>
              <th className={thClass}>Оценка ОКК</th>
              <th className={thClass}>Рекомендации</th>
              <th className={thClass}>Аудио</th>
              <th className={thClass}>Фрагмент</th>
              <th className={thClass}>
                <span className="sr-only">Удалить запись</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={11} className="px-3 py-6 text-center text-slate-500">
                  Загрузка…
                </td>
              </tr>
            ) : loadError ? (
              <tr>
                <td
                  colSpan={11}
                  className="px-3 py-6 text-center text-sm text-red-400"
                >
                  Не удалось загрузить данные: {loadError}. Проверьте, что бэкенд доступен через
                  прокси <code className="text-xs">/api/</code>.
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td
                  colSpan={11}
                  className="px-3 py-6 text-center text-sm text-slate-500"
                >
                  Пока нет записей. Завершите голосовой звонок или вызовите{" "}
                  <code className="text-xs">POST /api/chat/finalize</code>.
                </td>
              </tr>
            ) : (
              items.map((rec) => {
                const an = rec.analytics;
                const id = String(rec.id);
                const recShort = an ? snippet(an.recommendations, 100) : "—";
                const url = recordingUrl(id);
                return (
                  <tr
                    key={id}
                    className="cursor-pointer border-b border-slate-700/80 hover:bg-slate-800/50"
                    onClick={() => openTranscript(rec)}
                  >
                    
                    <td className={tdClass}>{rec.direction || "web"}</td>
                    <td className={tdClass}>{rec.remote_phone || "—"}</td>
                    <td className={tdClass}>{rec.status}</td>
                    <td className={tdClass}>{String(rec.duration)}</td>
                    <td className={`${tdClass} whitespace-nowrap text-slate-400`}>
                      {formatDateTimeRu(rec.created_at)}
                    </td>
                    <td className={tdClass}>{an ? String(an.score) : "—"}</td>
                    <td className={`${tdClass} max-w-[10rem]`}>
                      {an?.recommendations ? (
                        <span
                          className="line-clamp-3 text-slate-300"
                          title={an.recommendations}
                        >
                          {recShort}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className={tdClass} onClick={(e) => e.stopPropagation()}>
                      {rec.has_audio ? (
                        <div className="flex flex-col gap-1">
                          <audio
                            controls
                            preload="metadata"
                            src={url}
                            className="max-w-[200px]"
                          />
                          <div className="flex gap-2">
                            <a
                              href={url}
                              download
                              title="Скачать запись"
                              className="text-sky-400 hover:text-sky-300"
                            >
                              ⬇
                            </a>
                            <IconDeleteButton
                              title="Удалить только файл записи"
                              className="border-amber-900/50 text-amber-400 hover:bg-amber-950/30"
                              onClick={(e) => onDeleteRecording(e, id)}
                            />
                          </div>
                        </div>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className={`${tdClass} max-w-[14rem] text-xs text-slate-400`}>
                      {snippet(rec.transcript_text, 120)}
                    </td>
                    <td className={tdClass} onClick={(e) => e.stopPropagation()}>
                      <IconDeleteButton
                        title="Удалить диалог целиком"
                        onClick={(e) => onDeleteCall(e, id)}
                      />
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {transcriptOpen && transcriptRec && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 bg-black/60"
            aria-label="Закрыть"
            onClick={closeTranscript}
          />
          <div
            className="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-[min(100%-2rem,40rem)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-slate-600 bg-slate-900 shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="call-transcript-title"
          >
            <div className="flex shrink-0 items-center justify-between border-b border-slate-700 px-4 py-3">
              <h2
                id="call-transcript-title"
                className="m-0 text-lg font-semibold text-white"
              >
                Транскрипт диалога
              </h2>
              <button
                type="button"
                className="text-2xl leading-none text-slate-400 hover:text-white"
                aria-label="Закрыть"
                onClick={closeTranscript}
              >
                ×
              </button>
            </div>
            <p className="mb-0 border-b border-slate-800 px-4 py-2 text-sm text-slate-400">
              Сессия: {transcriptRec.session_id || "—"} · {formatDateTimeRu(transcriptRec.created_at)}
            </p>
            <div className="max-h-[65vh] overflow-y-auto whitespace-pre-wrap break-words p-4 text-sm text-slate-200">
              {(transcriptRec.transcript_text || "").trim()
                ? transcriptRec.transcript_text
                : "Транскрипт пуст."}
            </div>
          </div>
        </>
      )}

      <section className="mt-10 rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <h3 className="text-sm font-medium text-slate-300">Проверка API</h3>
        <p className="mt-2 text-xs text-slate-500">
          Запрос: <code className="text-slate-400">GET /api/health</code> — заголовки Битрикс подставляет{" "}
          <code className="text-slate-400">api/client.js</code>.
        </p>
        <p className="mt-2 text-sm text-slate-400">
          Статус: <span className="text-white">{apiStatus}</span>
        </p>
        {apiHint && (
          <pre className="mt-3 max-h-40 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-300">
            {apiHint}
          </pre>
        )}
      </section>
        </>
      )}
    </div>
  );
}
