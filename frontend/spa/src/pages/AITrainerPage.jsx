import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../api/client.js";
import { TrainerScenariosPanel } from "../components/trainer/TrainerScenariosPanel.jsx";

function formatErr(err) {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (d != null) return JSON.stringify(d);
  return err?.message ?? String(err);
}

const tabBtn = (active) =>
  `rounded-t-lg border px-4 py-2 text-sm font-medium transition-colors ${
    active
      ? "border-slate-600 border-b-transparent bg-slate-800/90 text-white"
      : "border-transparent text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
  }`;

const inputClass =
  "w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500";
const labelClass = "mb-1 block text-sm font-medium text-slate-200";

export function AITrainerPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const tab = useMemo(() => {
    return searchParams.get("tab") === "scenarios" ? "scenarios" : "simulation";
  }, [searchParams]);

  const setTab = (next) => {
    if (next === "scenarios") {
      setSearchParams({ tab: "scenarios" }, { replace: true });
    } else {
      setSearchParams({}, { replace: true });
    }
  };

  const [scenarios, setScenarios] = useState([]);
  const [loadMetaErr, setLoadMetaErr] = useState(null);

  const [scenarioId, setScenarioId] = useState("");
  const [managerPhone, setManagerPhone] = useState("");
  const [simLoading, setSimLoading] = useState(false);
  const [simErr, setSimErr] = useState(null);
  const [simStatus, setSimStatus] = useState(null);

  const loadScenarios = useCallback(async () => {
    setLoadMetaErr(null);
    try {
      const { data } = await api.get("/scenarios");
      const s = Array.isArray(data) ? data : [];
      setScenarios(s);
      setScenarioId((prev) => (prev || !s.length ? prev : String(s[0].id)));
    } catch (e) {
      setLoadMetaErr(formatErr(e));
    }
  }, []);

  useEffect(() => {
    void loadScenarios();
  }, [loadScenarios]);

  const onSimulate = async (e) => {
    e.preventDefault();
    if (!scenarioId.trim()) {
      setSimErr("Выберите сценарий (персону).");
      return;
    }
    if (!managerPhone.trim()) {
      setSimErr("Укажите добавочный номер / SIP.");
      return;
    }
    setSimLoading(true);
    setSimErr(null);
    setSimStatus(null);
    try {
      const { data } = await api.post("/trainer/simulate", {
        manager_phone: managerPhone.trim(),
        scenario_id: scenarioId.trim(),
      });
      setSimStatus(data);
    } catch (err) {
      setSimErr(formatErr(err));
    } finally {
      setSimLoading(false);
    }
  };

  return (
    <div className="max-w-4xl text-slate-100">
      <h1 className="mb-2 text-2xl font-bold text-white">ИИ-тренер отдела продаж</h1>
      <p className="mb-6 text-sm text-slate-400">
        Голосовая симуляция: Asterisk звонит менеджеру, ИИ отыгрывает роль клиента. Персоны и возражения создаются на
        вкладке «Сценарии». Аналитика по методикам (BANT/MEDDIC) — в разделе «ИИ-контроль (QA)», вкладка «Аналитика
        звонков».
      </p>

      {loadMetaErr && tab === "simulation" && (
        <p className="mb-4 rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">
          {loadMetaErr}
        </p>
      )}

      <div
        className="mb-0 flex flex-wrap gap-1 border-b border-slate-600"
        role="tablist"
        aria-label="Режим тренера"
      >
        <button
          type="button"
          role="tab"
          aria-selected={tab === "simulation"}
          className={tabBtn(tab === "simulation")}
          onClick={() => setTab("simulation")}
        >
          Голосовая симуляция
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "scenarios"}
          className={tabBtn(tab === "scenarios")}
          onClick={() => setTab("scenarios")}
        >
          Сценарии
        </button>
      </div>

      {tab === "simulation" && (
        <div
          className="rounded-b-xl rounded-tr-xl border border-t-0 border-slate-600 bg-slate-800/30 p-5"
          role="tabpanel"
        >
          <form className="space-y-4" onSubmit={onSimulate}>
            <div>
              <label className={labelClass} htmlFor="trainer-scenario">
                Персона клиента (сценарий тренажёра)
              </label>
              <select
                id="trainer-scenario"
                className={inputClass}
                value={scenarioId}
                onChange={(e) => setScenarioId(e.target.value)}
              >
                {scenarios.length === 0 ? (
                  <option value="">Нет сценариев — создайте на вкладке «Сценарии»</option>
                ) : (
                  scenarios.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title}
                    </option>
                  ))
                )}
              </select>
            </div>
            <div>
              <label className={labelClass} htmlFor="trainer-extension">
                Добавочный номер менеджера (SIP / PJSIP)
              </label>
              <input
                id="trainer-extension"
                type="text"
                className={inputClass}
                placeholder="Например 1001 или user@domain"
                value={managerPhone}
                onChange={(e) => setManagerPhone(e.target.value)}
              />
              <p className="mt-1 text-xs text-slate-500">
                В Asterisk будет вызван endpoint{" "}
                <code className="rounded bg-slate-900 px-1">PJSIP/&lt;номер&gt;</code>
              </p>
            </div>
            {simErr && <p className="text-sm text-red-400">{simErr}</p>}
            <button
              type="submit"
              className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
              disabled={simLoading || !scenarios.length}
            >
              {simLoading ? "⏳ Инициация…" : "▶ Начать тренировку"}
            </button>
          </form>

          {simStatus && (
            <div
              className={`mt-6 flex items-start gap-3 rounded-xl border p-4 text-sm ${
                simStatus.status === "initiated"
                  ? "border-emerald-800/60 bg-emerald-950/20 text-emerald-100"
                  : "border-amber-800/60 bg-amber-950/20 text-amber-100"
              }`}
            >
              <span className="text-xl" aria-hidden>
                {simStatus.status === "initiated" ? "✓" : "⚠"}
              </span>
              <div>
                <div className="font-semibold">
                  {simStatus.status === "initiated" ? "Звонок инициирован" : "Ошибка инициации"}
                </div>
                <p className="mt-1 text-slate-300">{simStatus.message}</p>
                <p className="mt-2 font-mono text-xs text-slate-400">
                  session_id: {simStatus.session_id}
                  {simStatus.channel_id ? ` · channel: ${simStatus.channel_id}` : ""}
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "scenarios" && (
        <TrainerScenariosPanel
          onScenariosChanged={() => {
            void loadScenarios();
          }}
        />
      )}
    </div>
  );
}
