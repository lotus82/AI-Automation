import { useEffect, useState } from "react";
import api from "../api/client.js";

/**
 * QA-аналитика транскрипций (ИИ-контроль отдела продаж).
 * Пример запроса к FastAPI — замените путь на реальный эндпоинт, когда появится в бэкенде.
 */
export function QAPage() {
  const [status, setStatus] = useState("idle");
  const [hint, setHint] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setStatus("loading");
      try {
        const { data } = await api.get("/health");
        if (!cancelled) {
          setHint(typeof data === "object" ? JSON.stringify(data) : String(data));
          setStatus("ok");
        }
      } catch (e) {
        if (!cancelled) {
          setHint(e?.message || "Ошибка сети");
          setStatus("error");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-white">ИИ-контроль отдела продаж</h2>
        <p className="mt-1 text-slate-400">
          QA-аналитика транскрипций и рекомендации ОКК. Здесь позже подключите списки записей,
          фильтры и графики.
        </p>
      </div>

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
        <h3 className="text-sm font-medium text-slate-300">Проверка API (заглушка)</h3>
        <p className="mt-2 text-xs text-slate-500">
          Запрос: <code className="text-slate-400">GET /api/health</code> — заголовки Битрикс подставляет{" "}
          <code className="text-slate-400">api/client.js</code>.
        </p>
        <p className="mt-2 text-sm text-slate-400">
          Статус: <span className="text-white">{status}</span>
        </p>
        {hint && (
          <pre className="mt-3 max-h-40 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-300">
            {hint}
          </pre>
        )}
      </section>
    </div>
  );
}
