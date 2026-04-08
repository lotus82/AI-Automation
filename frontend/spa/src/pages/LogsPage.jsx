import { useCallback, useEffect, useState } from "react";
import api from "../api/client.js";

const TOKEN_STORAGE = "sales_ai_admin_logs_token";

function formatApiDetail(err) {
  const body = err?.response?.data;
  const det = body?.detail;
  if (typeof det === "string") return det;
  if (Array.isArray(det)) {
    return det.map((x) => (typeof x === "object" && x != null ? x.msg ?? x : x)).join("; ");
  }
  if (det != null) return JSON.stringify(det);
  return err?.message ?? String(err);
}

export function LogsPage() {
  const [token, setToken] = useState(() =>
    typeof sessionStorage !== "undefined" ? sessionStorage.getItem(TOKEN_STORAGE) || "" : "",
  );
  const [tokenInput, setTokenInput] = useState("");
  const [containers, setContainers] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [tail, setTail] = useState(500);
  const [logText, setLogText] = useState("");
  const [listErr, setListErr] = useState("");
  const [logErr, setLogErr] = useState("");
  const [listLoading, setListLoading] = useState(false);
  const [logLoading, setLogLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const saveToken = () => {
    const t = tokenInput.trim();
    setToken(t);
    if (typeof sessionStorage !== "undefined") {
      if (t) sessionStorage.setItem(TOKEN_STORAGE, t);
      else sessionStorage.removeItem(TOKEN_STORAGE);
    }
    setListErr("");
    setLogErr("");
  };

  const loadContainers = useCallback(async () => {
    if (!token) {
      setListErr("Сохраните токен (совпадает с ADMIN_LOGS_TOKEN в .env).");
      return;
    }
    setListLoading(true);
    setListErr("");
    try {
      const { data } = await api.get("/admin/container-logs/containers", {
        headers: { "X-Admin-Logs-Token": token },
      });
      const list = Array.isArray(data?.containers) ? data.containers : [];
      setContainers(list);
      setSelectedId((prev) => {
        if (!list.length) return "";
        if (prev && list.some((c) => c.id === prev)) return prev;
        return list[0].id;
      });
    } catch (e) {
      console.error(e);
      setListErr(formatApiDetail(e) || "Не удалось получить список контейнеров");
      setContainers([]);
    } finally {
      setListLoading(false);
    }
  }, [token]);

  const loadLogs = useCallback(async () => {
    if (!token || !selectedId) return;
    setLogLoading(true);
    setLogErr("");
    try {
      const { data } = await api.get(`/admin/container-logs/${encodeURIComponent(selectedId)}/logs`, {
        headers: { "X-Admin-Logs-Token": token },
        params: { tail, timestamps: true },
      });
      setLogText(typeof data?.text === "string" ? data.text : "");
    } catch (e) {
      console.error(e);
      setLogErr(formatApiDetail(e) || "Ошибка загрузки логов");
      setLogText("");
    } finally {
      setLogLoading(false);
    }
  }, [token, selectedId, tail]);

  useEffect(() => {
    setTokenInput(token);
  }, [token]);

  useEffect(() => {
    if (token) loadContainers();
  }, [token, loadContainers]);

  useEffect(() => {
    if (!autoRefresh || !token || !selectedId) return;
    const id = window.setInterval(() => {
      loadLogs();
    }, 5000);
    return () => window.clearInterval(id);
  }, [autoRefresh, token, selectedId, loadLogs]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Логи контейнеров</h1>
        <p className="mt-1 text-sm text-slate-400">
          Для VPS: в <code className="rounded bg-slate-800 px-1 text-xs">.env</code> задайте{" "}
          <code className="rounded bg-slate-800 px-1 text-xs">ADMIN_LOGS_TOKEN</code>, перезапустите{" "}
          <code className="rounded bg-slate-800 px-1 text-xs">web</code> и смонтируйте Docker-сокет (см.{" "}
          <code className="rounded bg-slate-800 px-1 text-xs">docker-compose.prod.yml</code>).
        </p>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 space-y-3">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Токен доступа</div>
        <div className="flex flex-wrap gap-2">
          <input
            type="password"
            autoComplete="off"
            className="min-w-[12rem] flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
            placeholder="Тот же, что ADMIN_LOGS_TOKEN на сервере"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
          />
          <button
            type="button"
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            onClick={saveToken}
          >
            Сохранить
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs text-slate-500">Контейнер</label>
          <select
            className="mt-1 min-w-[16rem] rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            disabled={!containers.length}
          >
            {containers.length === 0 ? (
              <option value="">— нет данных —</option>
            ) : (
              containers.map((c) => (
                <option key={c.id} value={c.id}>
                  {(c.names && c.names[0]) || c.short_id} ({c.state}) — {c.image}
                </option>
              ))
            )}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500">Строк (tail)</label>
          <input
            type="number"
            min={1}
            max={20000}
            className="mt-1 w-28 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
            value={tail}
            onChange={(e) => setTail(Number(e.target.value) || 500)}
          />
        </div>
        <button
          type="button"
          disabled={listLoading || !token}
          className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
          onClick={() => loadContainers()}
        >
          {listLoading ? "Список…" : "Обновить список"}
        </button>
        <button
          type="button"
          disabled={logLoading || !token || !selectedId}
          className="rounded-lg bg-slate-700 px-4 py-2 text-sm text-white hover:bg-slate-600 disabled:opacity-50"
          onClick={() => loadLogs()}
        >
          {logLoading ? "Загрузка…" : "Загрузить логи"}
        </button>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-400">
          <input
            type="checkbox"
            className="rounded border-slate-600 text-emerald-500"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
          />
          Авто каждые 5 с
        </label>
      </div>

      {listErr ? <p className="text-sm text-red-400">{listErr}</p> : null}
      {logErr ? <p className="text-sm text-red-400">{logErr}</p> : null}

      <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
        <pre className="max-h-[min(70vh,48rem)] overflow-auto p-4 font-mono text-xs leading-relaxed text-slate-300 whitespace-pre-wrap break-all">
          {logText || (logLoading ? "…" : "Нажмите «Загрузить логи» или включите автообновление.")}
        </pre>
      </div>
    </div>
  );
}
