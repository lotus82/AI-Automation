import { useCallback, useEffect, useRef, useState } from "react";
import api from "../api/client.js";

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("ru-RU");
}

/** URL WebSocket мониторинга: учёт VITE_API_BASE_URL и текущего хоста (в т.ч. Vite proxy). */
function getMonitoringWebSocketUrl() {
  const raw = import.meta.env.VITE_API_BASE_URL;
  if (raw != null && String(raw).trim() !== "") {
    const base = String(raw).trim().replace(/\/$/, "");
    const httpUrl = base.startsWith("http") ? base : `http://${base}`;
    const u = new URL(httpUrl);
    const wsProto = u.protocol === "https:" ? "wss:" : "ws:";
    return `${wsProto}//${u.host}/api/ws/monitoring`;
  }
  const p = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${p}//${window.location.host}/api/ws/monitoring`;
}

function upsertSessionRow(list, sessionId, preview, atIso, userLabel) {
  const existing = list.find((r) => r.session_id === sessionId);
  const row = {
    session_id: sessionId,
    user_label:
      userLabel != null && String(userLabel).trim() !== ""
        ? String(userLabel).trim()
        : existing?.user_label ?? null,
    last_preview: preview,
    last_at: atIso,
  };
  return [row, ...list.filter((r) => r.session_id !== sessionId)];
}

function sessionTitleLine(sessionId, mapLookup) {
  const rec = mapLookup?.get?.(sessionId);
  const name = rec?.user_label ? String(rec.user_label).trim() : "";
  return `Сессия: ${sessionId}${name ? ` (${name})` : ""}`;
}

export function BotsPage() {
  const [activeTab, setActiveTab] = useState("max");
  const [rows, setRows] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(null);

  const [wsStatus, setWsStatus] = useState({ text: "", isError: false });

  const [historyOpen, setHistoryOpen] = useState(false);
  const [historySessionId, setHistorySessionId] = useState(null);
  const [historyMessages, setHistoryMessages] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);

  const historyThreadRef = useRef(null);
  const selectedSessionRef = useRef(null);
  selectedSessionRef.current = historySessionId;

  const rowsMap = useRef(new Map());
  rowsMap.current = new Map(rows.map((r) => [r.session_id, r]));

  const loadSessions = useCallback(async () => {
    setListLoading(true);
    setListError(null);
    try {
      const { data } = await api.get("/chats");
      const items = data?.items || [];
      setRows(
        items.map((it) => ({
          session_id: it.session_id,
          user_label: it.user_label ?? null,
          last_preview: it.last_preview ?? "—",
          last_at: it.last_at,
        }))
      );
    } catch (e) {
      setListError(e?.message || String(e));
      setRows([]);
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const openHistory = useCallback(async (sessionId) => {
    setHistorySessionId(sessionId);
    setHistoryOpen(true);
    setHistoryLoading(true);
    setHistoryError(null);
    setHistoryMessages([]);
    try {
      const { data } = await api.get(
        `/chats/${encodeURIComponent(sessionId)}`
      );
      setHistoryMessages(data?.messages || []);
    } catch (e) {
      setHistoryError(e?.message || String(e));
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const closeHistory = useCallback(() => {
    setHistoryOpen(false);
    setHistorySessionId(null);
    setHistoryMessages([]);
    setHistoryError(null);
  }, []);

  const refreshHistoryIfOpen = useCallback(
    async (sessionId) => {
      if (selectedSessionRef.current !== sessionId) return;
      try {
        const { data } = await api.get(
          `/chats/${encodeURIComponent(sessionId)}`
        );
        setHistoryMessages(data?.messages || []);
      } catch {
        /* как в vanilla: игнорируем */
      }
    },
    []
  );

  useEffect(() => {
    if (!historyOpen || !historyMessages.length) return;
    const el = historyThreadRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight;
      });
    });
  }, [historyOpen, historyMessages]);

  useEffect(() => {
    let ws = null;
    let pingTimer = null;
    let reconnectTimer = null;
    let stopped = false;

    const connect = () => {
      if (stopped) return;
      setWsStatus({ text: "Подключение к мониторингу…", isError: false });
      try {
        ws = new WebSocket(getMonitoringWebSocketUrl());
      } catch (e) {
        setWsStatus({
          text: "Не удалось открыть WebSocket.",
          isError: true,
        });
        reconnectTimer = window.setTimeout(connect, 5000);
        return;
      }

      ws.onopen = () => {
        if (stopped) {
          try {
            ws.close();
          } catch {
            /* ignore */
          }
          return;
        }
        setWsStatus({ text: "Мониторинг: соединение активно.", isError: false });
        if (pingTimer) clearInterval(pingTimer);
        pingTimer = window.setInterval(() => {
          if (ws?.readyState === WebSocket.OPEN) {
            try {
              ws.send("ping");
            } catch {
              /* ignore */
            }
          }
        }, 25000);
      };

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type !== "new_message") return;
          const sid = data.session_id;
          const preview = String(data.content || "").slice(0, 280);
          const now = new Date().toISOString();
          const uinfo = data.user_info || "";
          setRows((prev) =>
            upsertSessionRow(prev, sid, preview, now, uinfo || null)
          );
          const openSid = selectedSessionRef.current;
          if (openSid === sid) {
            refreshHistoryIfOpen(sid);
          }
        } catch (e) {
          console.warn(e);
        }
      };

      ws.onerror = () => {
        setWsStatus({
          text: "Ошибка WebSocket (проверьте прокси и HTTPS).",
          isError: true,
        });
      };

      ws.onclose = () => {
        if (stopped) return;
        setWsStatus({
          text: "Соединение мониторинга закрыто. Переподключение через 5 с…",
          isError: true,
        });
        if (pingTimer) {
          clearInterval(pingTimer);
          pingTimer = null;
        }
        reconnectTimer = window.setTimeout(connect, 5000);
      };
    };

    connect();

    return () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingTimer) clearInterval(pingTimer);
      if (ws) {
        try {
          ws.onclose = null;
          ws.close();
        } catch {
          /* ignore */
        }
      }
    };
  }, [refreshHistoryIfOpen]);

  useEffect(() => {
    if (!historyOpen) return;
    const onKey = (e) => {
      if (e.key === "Escape") closeHistory();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [historyOpen, closeHistory]);

  const switchTab = (key) => {
    closeHistory();
    setActiveTab(key);
  };

  const tabBtnClass = (on) =>
    `inline-flex items-center gap-2 rounded-t-lg border px-4 py-2 text-sm font-medium transition-colors ${
      on
        ? "border-slate-600 border-b-transparent bg-slate-800/80 text-white"
        : "border-transparent text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
    }`;

  return (
    <div className="max-w-5xl text-slate-100">
      <h1 className="mb-2 flex items-center gap-2 text-2xl font-bold text-white">
        <span aria-hidden>🤖</span>
        Мониторинг чат-ботов
      </h1>
      <p className="mb-6 text-sm leading-relaxed text-slate-300">
        Активные сессии (MAX, веб-чат, голос — общая память). Обновление строк
        в реальном времени через WebSocket. Полная история хранится в
        PostgreSQL.
      </p>

      <div
        className="mb-0 flex flex-wrap gap-1 border-b border-slate-600"
        role="tablist"
        aria-label="Канал бота"
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "max"}
          id="bots-tab-btn-max"
          className={tabBtnClass(activeTab === "max")}
          onClick={() => switchTab("max")}
        >
          <img
            src="/static/img/Max_logo.svg"
            alt=""
            className="inline h-4 w-4"
          />
          MAX
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "telegram"}
          id="bots-tab-btn-telegram"
          className={tabBtnClass(activeTab === "telegram")}
          onClick={() => switchTab("telegram")}
        >
          <span className="text-sky-400" aria-hidden>
            ✈
          </span>
          Telegram
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "vk"}
          id="bots-tab-btn-vk"
          className={tabBtnClass(activeTab === "vk")}
          onClick={() => switchTab("vk")}
        >
          <span className="text-blue-400" aria-hidden>
            VK
          </span>
        </button>
      </div>

      <div
        id="bots-tab-max"
        role="tabpanel"
        aria-labelledby="bots-tab-btn-max"
        hidden={activeTab !== "max"}
        className="border border-t-0 border-slate-600 rounded-b-xl rounded-tr-xl bg-slate-800/30 p-4"
      >
        <p
          id="bots-ws-status"
          className={`mb-3 text-sm ${wsStatus.isError ? "text-red-400" : "text-emerald-400"}`}
          aria-live="polite"
        >
          {wsStatus.text}
        </p>

        <div className="overflow-x-auto rounded-lg border border-slate-700/80 bg-slate-900/40">
          <table className="w-full min-w-[480px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-600 text-xs uppercase tracking-wide text-slate-400">
                <th className="px-3 py-2 font-medium">Сессия / пользователь</th>
                <th className="px-3 py-2 font-medium">Последнее сообщение</th>
                <th className="px-3 py-2 font-medium">Время</th>
              </tr>
            </thead>
            <tbody>
              {listLoading ? (
                <tr id="bots-empty-row">
                  <td
                    colSpan={3}
                    className="px-3 py-6 text-center text-slate-500"
                  >
                    Загрузка…
                  </td>
                </tr>
              ) : listError ? (
                <tr>
                  <td
                    colSpan={3}
                    className="px-3 py-6 text-center text-red-400"
                  >
                    {listError}
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td
                    colSpan={3}
                    className="px-3 py-6 text-center text-slate-500"
                  >
                    Нет сохранённых сообщений. Напишите боту в MAX или в тестере
                    чата.
                  </td>
                </tr>
              ) : (
                rows.map((rec) => {
                  const title = rec.user_label
                    ? `${rec.user_label} (${rec.session_id})`
                    : rec.session_id;
                  return (
                    <tr
                      key={rec.session_id}
                      data-session-id={rec.session_id}
                      className="cursor-pointer border-b border-slate-700/80 hover:bg-slate-800/60"
                      onClick={() => openHistory(rec.session_id)}
                    >
                      <td className="px-3 py-2 align-top font-mono text-xs text-sky-300">
                        {title}
                      </td>
                      <td className="max-w-md px-3 py-2 align-top text-slate-300">
                        {rec.last_preview || "—"}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 align-top text-slate-400">
                        {formatDate(rec.last_at)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div
        id="bots-tab-telegram"
        role="tabpanel"
        aria-labelledby="bots-tab-btn-telegram"
        hidden={activeTab !== "telegram"}
        className="rounded-b-xl rounded-tr-xl border border-t-0 border-slate-600 bg-slate-800/40 p-5"
      >
        <p className="m-0 text-sm text-slate-300">
          <span className="text-sky-400" aria-hidden>
            ✈{" "}
          </span>
          Мониторинг Telegram-бота — <strong>в разработке</strong>. Сообщения
          уже обрабатываются бэкендом; здесь появится таблица сессий и история,
          аналогично вкладке MAX.
        </p>
      </div>

      <div
        id="bots-tab-vk"
        role="tabpanel"
        aria-labelledby="bots-tab-btn-vk"
        hidden={activeTab !== "vk"}
        className="rounded-b-xl rounded-tr-xl border border-t-0 border-slate-600 bg-slate-800/40 p-5"
      >
        <p className="m-0 text-sm text-slate-300">
          <span className="text-blue-400" aria-hidden>
            VK{" "}
          </span>
          Интеграция VK — <strong>в разработке</strong>. Вкладка зарезервирована
          под будущий мониторинг диалогов.
        </p>
      </div>

      {historyOpen && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 bg-black/60"
            aria-label="Закрыть"
            onClick={closeHistory}
          />
          <div
            id="bots-history-modal"
            className="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-[min(100%-2rem,32rem)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-slate-600 bg-slate-900 shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="bots-history-title"
          >
            <div className="flex shrink-0 items-start justify-between border-b border-slate-700 px-4 py-3">
              <div>
                <h2
                  id="bots-history-title"
                  className="text-lg font-semibold text-white"
                >
                  💬 История диалога
                </h2>
                <p
                  id="bots-history-session"
                  className="mt-1 text-sm text-slate-400"
                >
                  {historySessionId
                    ? sessionTitleLine(historySessionId, rowsMap.current)
                    : ""}
                </p>
              </div>
              <button
                type="button"
                id="bots-history-close"
                className="text-2xl leading-none text-slate-400 hover:text-white"
                aria-label="Закрыть"
                onClick={closeHistory}
              >
                ×
              </button>
            </div>
            <div
              id="bots-history-body"
              className="min-h-0 flex-1 overflow-y-auto p-4"
            >
              {historyLoading ? (
                <p className="text-center text-slate-500">Загрузка…</p>
              ) : historyError ? (
                <p className="text-center text-red-400">{historyError}</p>
              ) : historyMessages.length === 0 ? (
                <p className="text-center text-slate-500">Нет сообщений.</p>
              ) : (
                <div
                  ref={historyThreadRef}
                  className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto pr-1"
                  role="log"
                  aria-relevant="additions"
                  aria-label="Сообщения чата"
                >
                  {historyMessages.map((m) => {
                    const role = m.role || "";
                    const roleRu =
                      role === "user"
                        ? "Пользователь"
                        : role === "assistant"
                          ? "ИИ-агент"
                          : role;
                    const isUser = role === "user";
                    const isAssistant = role === "assistant";
                    return (
                      <div
                        key={m.id}
                        className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                          isUser
                            ? "ml-auto bg-sky-900/50 text-slate-100"
                            : isAssistant
                              ? "mr-auto bg-slate-800 text-slate-100"
                              : "mx-auto bg-amber-950/40 text-amber-100"
                        }`}
                      >
                        <div className="mb-1 text-xs text-slate-400">
                          {roleRu} · {formatDate(m.created_at)}
                        </div>
                        <div className="whitespace-pre-wrap break-words">
                          {m.content || ""}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
