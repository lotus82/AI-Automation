import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { BookOpen, ClipboardList, HeartPulse, Loader2 } from "lucide-react";

const card =
  "rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm shadow-slate-200/50";

function formatDate(d) {
  if (!d) return "—";
  try {
    return new Date(d).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
  } catch {
    return d;
  }
}

export function PatientMISPage() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  const [dDate, setDDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [dMetric, setDMetric] = useState("");
  const [dValue, setDValue] = useState("");
  const [dBusy, setDBusy] = useState(false);
  const [dMsg, setDMsg] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setErr("");
    try {
      const res = await fetch(`/api/public/mis/patient/${encodeURIComponent(id)}`);
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(typeof j?.detail === "string" ? j.detail : `Ошибка ${res.status}`);
      }
      setData(await res.json());
    } catch (e) {
      setErr(e?.message ?? String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const recentExams = useMemo(() => {
    const entries = data?.entries ?? [];
    return entries
      .filter((e) => e.type === "exam")
      .slice(0, 8);
  }, [data?.entries]);

  const submitDiary = async (e) => {
    e.preventDefault();
    if (!id) return;
    const metric = dMetric.trim();
    const value = dValue.trim();
    if (!metric || !value) {
      setDMsg("Укажите показатель и значение.");
      return;
    }
    setDBusy(true);
    setDMsg("");
    try {
      const res = await fetch(`/api/public/mis/patient/${encodeURIComponent(id)}/diary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entry_date: dDate, metric, value }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(typeof j?.detail === "string" ? j.detail : `Ошибка ${res.status}`);
      }
      setDMetric("");
      setDValue("");
      setDMsg("Запись отправлена врачу.");
      await load();
    } catch (e) {
      setDMsg(e?.message ?? String(e));
    } finally {
      setDBusy(false);
    }
  };

  if (loading) {
    return (
      <div className={`${card} flex items-center justify-center gap-2 py-16 text-slate-500`}>
        <Loader2 className="h-6 w-6 animate-spin text-teal-600" aria-hidden />
        Загрузка…
      </div>
    );
  }

  if (err) {
    return (
      <div className={`${card} border-red-200 bg-red-50/80 text-red-800`}>
        <p className="font-medium">Не удалось открыть карту</p>
        <p className="mt-1 text-sm">{err}</p>
      </div>
    );
  }

  const p = data?.patient;

  return (
    <div className="space-y-6">
      <section className={card}>
        <h1 className="text-lg font-semibold text-slate-900">{p?.full_name}</h1>
        <p className="mt-1 text-sm text-slate-600">
          Дата рождения: {formatDate(p?.birth_date)} · Тел.: {p?.phone || "—"}
        </p>
      </section>

      <section className={card}>
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <ClipboardList className="h-5 w-5 text-teal-600" strokeWidth={1.75} aria-hidden />
          Последние обследования
        </h2>
        {recentExams.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">Пока нет записей обследований.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {recentExams.map((e) => (
              <li key={e.id} className="rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-sm">
                <div className="flex flex-wrap justify-between gap-2 text-slate-700">
                  <span className="font-medium">{formatDate(e.entry_date)}</span>
                  <span className="rounded-full bg-teal-100 px-2 py-0.5 text-xs font-medium text-teal-800">Обследование</span>
                </div>
                {(e.conclusion || "").trim() ? (
                  <p className="mt-2 text-slate-700">{e.conclusion}</p>
                ) : null}
                {e.data && Object.keys(e.data).length > 0 ? (
                  <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-white p-2 text-xs text-slate-600 ring-1 ring-slate-100">
                    {JSON.stringify(e.data, null, 2)}
                  </pre>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={card}>
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <HeartPulse className="h-5 w-5 text-teal-600" strokeWidth={1.75} aria-hidden />
          Дневник здоровья
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Передайте показатели лечащему врачу (давление, самочувствие и т.д.).
        </p>
        <form onSubmit={submitDiary} className="mt-4 space-y-3">
          <label className="block text-xs font-medium text-slate-600">
            Дата
            <input
              type="date"
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-teal-500/30 focus:ring-2"
              value={dDate}
              onChange={(e) => setDDate(e.target.value)}
              required
            />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            Показатель
            <input
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-teal-500/30 focus:ring-2"
              placeholder="Например: артериальное давление"
              value={dMetric}
              onChange={(e) => setDMetric(e.target.value)}
            />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            Значение
            <input
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-teal-500/30 focus:ring-2"
              placeholder="Например: 120/80"
              value={dValue}
              onChange={(e) => setDValue(e.target.value)}
            />
          </label>
          {dMsg ? <p className="text-sm text-teal-800">{dMsg}</p> : null}
          <button
            type="submit"
            disabled={dBusy}
            className="w-full rounded-xl bg-teal-600 py-2.5 text-sm font-semibold text-white shadow-md shadow-teal-600/25 disabled:opacity-50"
          >
            {dBusy ? "Отправка…" : "Отправить врачу"}
          </button>
        </form>
      </section>

      <section className={card}>
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <BookOpen className="h-5 w-5 text-teal-600" strokeWidth={1.75} aria-hidden />
          Полезные материалы
        </h2>
        <ul className="mt-3 list-inside list-disc space-y-2 text-sm text-slate-700">
          <li>Соблюдайте назначенный режим лечения и дозировки препаратов.</li>
          <li>При ухудшении самочувствия обратитесь к врачу или вызовите скорую помощь (103).</li>
          <li>
            Официальные рекомендации:{" "}
            <a
              href="https://www.rosminzdrav.ru/"
              className="font-medium text-teal-700 underline decoration-teal-300 underline-offset-2"
              target="_blank"
              rel="noopener noreferrer"
            >
              Минздрав России
            </a>
          </li>
        </ul>
      </section>
    </div>
  );
}
