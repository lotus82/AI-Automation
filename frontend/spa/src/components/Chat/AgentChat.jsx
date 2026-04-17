import { useCallback, useEffect, useId, useRef, useState } from "react";
import { getBrowserIanaTimeZone } from "../../utils/clientTimeZone.js";

function newId() {
  return globalThis.crypto?.randomUUID?.() ?? `m-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function toHistoryRow(m) {
  return { role: m.role, content: m.content };
}

function payloadToText(parsed) {
  if (typeof parsed === "string") return parsed;
  if (parsed && typeof parsed === "object" && "error" in parsed) {
    const err = parsed.error;
    return typeof err === "string" ? err : JSON.stringify(parsed);
  }
  return "";
}

function isErrorPayload(parsed) {
  return (
    parsed !== null &&
    typeof parsed === "object" &&
    "error" in parsed &&
    typeof parsed.error === "string"
  );
}

function drainSseBuffer(buffer) {
  const lines = [];
  let rest = buffer;
  let sep;
  while ((sep = rest.indexOf("\n\n")) !== -1) {
    const block = rest.slice(0, sep);
    rest = rest.slice(sep + 2);
    for (const rawLine of block.split("\n")) {
      const line = rawLine.replace(/\r$/, "");
      if (line.startsWith("data:")) {
        lines.push(line.slice(5).trimStart());
      }
    }
  }
  return { lines, rest };
}

export function AgentChat({ integrationIds, apiBaseUrl = "/api", className = "" }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const listEndRef = useRef(null);
  const formId = useId();

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      const userMsg = { id: newId(), role: "user", content: trimmed };
      const assistantId = newId();
      const assistantShell = { id: assistantId, role: "assistant", content: "" };

      const historyPayload = messages.map(toHistoryRow);

      setMessages((prev) => [...prev, userMsg, assistantShell]);
      setInput("");
      setIsStreaming(true);

      const url = `${apiBaseUrl.replace(/\/$/, "")}/v1/chat/stream`;
      const tz = getBrowserIanaTimeZone();

      let response;
      try {
        response = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
            ...(tz ? { "X-Client-Timezone": tz } : {}),
          },
          body: JSON.stringify({
            message: trimmed,
            integration_ids: integrationIds,
            history: historyPayload,
          }),
        });
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === "assistant" && last.id === assistantId) {
            next[next.length - 1] = {
              ...last,
              content: `Сеть: не удалось выполнить запрос (${msg}).`,
            };
          }
          return next;
        });
        setIsStreaming(false);
        return;
      }

      if (!response.ok) {
        let detail = `Ошибка ${response.status}`;
        try {
          const ct = response.headers.get("content-type") ?? "";
          if (ct.includes("application/json")) {
            const j = await response.json();
            if (j?.detail != null) detail = String(j.detail);
          } else {
            const t = await response.text();
            if (t) detail = t.slice(0, 500);
          }
        } catch {
          /* оставляем detail по статусу */
        }
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === "assistant" && last.id === assistantId) {
            next[next.length - 1] = { ...last, content: detail };
          }
          return next;
        });
        setIsStreaming(false);
        return;
      }

      const body = response.body;
      if (!body) {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === "assistant" && last.id === assistantId) {
            next[next.length - 1] = {
              ...last,
              content: "Пустой ответ: нет тела стрима.",
            };
          }
          return next;
        });
        setIsStreaming(false);
        return;
      }

      const reader = body.getReader();
      const decoder = new TextDecoder("utf-8");
      let carry = "";

      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          carry += decoder.decode(value, { stream: true });
          const { lines, rest } = drainSseBuffer(carry);
          carry = rest;

          for (const dataLine of lines) {
            let parsed;
            try {
              parsed = JSON.parse(dataLine);
            } catch {
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role === "assistant" && last.id === assistantId) {
                  next[next.length - 1] = {
                    ...last,
                    content: last.content + dataLine,
                  };
                }
                return next;
              });
              continue;
            }

            if (isErrorPayload(parsed)) {
              const errText = payloadToText(parsed);
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role === "assistant" && last.id === assistantId) {
                  next[next.length - 1] = {
                    ...last,
                    content: last.content + (last.content ? "\n" : "") + errText,
                  };
                }
                return next;
              });
              continue;
            }

            const piece = payloadToText(parsed);
            if (!piece) continue;

            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.role === "assistant" && last.id === assistantId) {
                next[next.length - 1] = { ...last, content: last.content + piece };
              }
              return next;
            });
          }
        }

        if (carry.trim()) {
          const { lines } = drainSseBuffer(carry + "\n\n");
          for (const dataLine of lines) {
            try {
              const parsed = JSON.parse(dataLine);
              const piece = payloadToText(parsed);
              if (!piece || isErrorPayload(parsed)) continue;
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role === "assistant" && last.id === assistantId) {
                  next[next.length - 1] = { ...last, content: last.content + piece };
                }
                return next;
              });
            } catch {
              /* ignore trailing garbage */
            }
          }
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === "assistant" && last.id === assistantId) {
            next[next.length - 1] = {
              ...last,
              content: last.content + (last.content ? "\n" : "") + `Ошибка чтения стрима: ${msg}`,
            };
          }
          return next;
        });
      } finally {
        setIsStreaming(false);
        try {
          reader.releaseLock();
        } catch {
          /* уже освобождён */
        }
      }
    },
    [apiBaseUrl, integrationIds, isStreaming, messages],
  );

  const onSubmit = (e) => {
    e.preventDefault();
    void sendMessage(input);
  };

  const last = messages[messages.length - 1];
  const awaitingFirstChunk = isStreaming && last?.role === "assistant" && last.content.length === 0;

  return (
    <div
      className={`flex h-full min-h-[22rem] max-h-[min(70vh,36rem)] flex-col rounded-2xl border border-slate-700/80 bg-slate-900/50 shadow-lg backdrop-blur-sm ${className}`}
    >
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <p className="text-center text-sm text-slate-500">
            Напишите сообщение — ответ придёт потоком (SSE).
          </p>
        ) : null}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow ${
                m.role === "user"
                  ? "bg-emerald-700/90 text-white"
                  : "border border-slate-600/80 bg-slate-800/90 text-slate-100"
              }`}
            >
              {m.content ? (
                <span className="whitespace-pre-wrap break-words">{m.content}</span>
              ) : m.role === "assistant" && isStreaming ? (
                <span className="inline-flex items-center gap-2 text-slate-400">
                  <span
                    className="inline-block size-3.5 shrink-0 animate-spin rounded-full border-2 border-slate-500 border-t-emerald-400"
                    aria-hidden
                  />
                  <span className="animate-pulse">Агент думает…</span>
                  <span className="font-mono text-emerald-400/90 animate-pulse" aria-hidden>
                    ▍
                  </span>
                </span>
              ) : null}
            </div>
          </div>
        ))}
        <div ref={listEndRef} />
      </div>

      <form
        id={formId}
        onSubmit={onSubmit}
        className="border-t border-slate-700/80 bg-slate-950/60 p-3"
      >
        <div className="flex gap-2">
          <label htmlFor={`${formId}-input`} className="sr-only">
            Сообщение
          </label>
          <input
            id={`${formId}-input`}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isStreaming}
            placeholder="Сообщение…"
            className="min-w-0 flex-1 rounded-xl border border-slate-600 bg-slate-950 px-4 py-2.5 text-sm text-white placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
            autoComplete="off"
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="shrink-0 rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Отправить
          </button>
        </div>
        {awaitingFirstChunk ? (
          <p className="mt-2 text-xs text-slate-500">Вызов инструментов и подготовка ответа…</p>
        ) : null}
      </form>
    </div>
  );
}
