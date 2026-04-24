import { CalendarDays, Save } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import Calendar from "react-calendar";
import { Navigate } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import api from "../../api/client.js";
import { useAuthStore } from "../../store/authStore.js";
import {
  BTN_SAVE,
  BTN_SAVE_COMPACT,
  ICON_BTN,
  PAGE_SHELL,
  PAGE_TEXT,
  TAB_ROW,
  tabBtn,
} from "../../styles/pageLayout.js";
import { formatDateTimeRu } from "../../utils/dateTimeFormat.js";
import "react-calendar/dist/Calendar.css";
import "./bookingsCalendar.css";

function pad2(n) {
  return String(n).padStart(2, "0");
}

function toYmd(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function startOfWeek(d) {
  const x = new Date(d);
  const day = x.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  x.setDate(x.getDate() + diff);
  x.setHours(0, 0, 0, 0);
  return x;
}

function addDays(d, n) {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function formatApiDetail(d) {
  if (d == null) return "";
  if (typeof d === "string") return d;
  return JSON.stringify(d);
}

export function BookingsPage() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const canAccess = useMemo(() => {
    if (!user) return false;
    if (["super_admin", "org_admin", "director"].includes(user.role)) return true;
    return (user.sections || []).includes("bookings");
  }, [user]);

  const [tab, setTab] = useState("calendar");
  const [calView, setCalView] = useState("month");
  const [selectedDate, setSelectedDate] = useState(() => new Date());
  const [appointments, setAppointments] = useState([]);
  const [busySlots, setBusySlots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [blockOpen, setBlockOpen] = useState(false);
  const [blockStart, setBlockStart] = useState("");
  const [blockEnd, setBlockEnd] = useState("");
  const [blockReason, setBlockReason] = useState("");
  const [detailApp, setDetailApp] = useState(null);

  const [cfgWh, setCfgWh] = useState({});
  const [cfgDur, setCfgDur] = useState(30);
  const [cfgLoading, setCfgLoading] = useState(false);
  const [cfgSaving, setCfgSaving] = useState(false);

  const [statsFrom, setStatsFrom] = useState(() => {
    const t = new Date();
    t.setDate(1);
    return toYmd(t);
  });
  const [statsTo, setStatsTo] = useState(() => toYmd(new Date()));
  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(false);

  const [miniChatDraft, setMiniChatDraft] = useState("");
  const [miniChatSaving, setMiniChatSaving] = useState(false);
  useEffect(() => {
    setMiniChatDraft((user?.miniapp_chat_id || "").trim());
  }, [user?.miniapp_chat_id]);

  const rangeForView = useMemo(() => {
    if (calView === "day") {
      const a = new Date(selectedDate);
      return { from: toYmd(a), to: toYmd(a) };
    }
    if (calView === "week") {
      const ws = startOfWeek(selectedDate);
      const we = addDays(ws, 6);
      return { from: toYmd(ws), to: toYmd(we) };
    }
    const y = selectedDate.getFullYear();
    const m = selectedDate.getMonth();
    const from = new Date(y, m, 1);
    const to = new Date(y, m + 1, 0);
    return { from: toYmd(from), to: toYmd(to) };
  }, [calView, selectedDate]);

  const loadCalendarData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { from, to } = rangeForView;
      const [aRes, bRes] = await Promise.all([
        api.get("/bookings/appointments", { params: { from, to } }),
        api.get("/bookings/busy-slots", { params: { from, to } }),
      ]);
      setAppointments(Array.isArray(aRes.data) ? aRes.data : []);
      setBusySlots(Array.isArray(bRes.data) ? bRes.data : []);
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [rangeForView]);

  useEffect(() => {
    if (!canAccess || tab !== "calendar") return;
    loadCalendarData();
  }, [canAccess, tab, loadCalendarData]);

  const loadConfig = useCallback(async () => {
    setCfgLoading(true);
    try {
      const { data } = await api.get("/bookings/config");
      setCfgWh(data.working_hours && typeof data.working_hours === "object" ? data.working_hours : {});
      setCfgDur(Number(data.appointment_duration) || 30);
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    } finally {
      setCfgLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!canAccess || tab !== "settings") return;
    loadConfig();
  }, [canAccess, tab, loadConfig]);

  const saveConfig = async () => {
    setCfgSaving(true);
    setError("");
    try {
      await api.put("/bookings/config", {
        working_hours: cfgWh,
        appointment_duration: cfgDur,
      });
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    } finally {
      setCfgSaving(false);
    }
  };

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    setError("");
    try {
      const { data } = await api.get("/bookings/stats", {
        params: { from: statsFrom, to: statsTo },
      });
      setStats(data);
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    } finally {
      setStatsLoading(false);
    }
  }, [statsFrom, statsTo]);

  useEffect(() => {
    if (!canAccess || tab !== "analytics") return;
    loadStats();
  }, [canAccess, tab, loadStats]);

  const submitBlock = async () => {
    if (!blockStart || !blockEnd) return;
    setError("");
    try {
      await api.post("/bookings/busy-slots", {
        start_time: new Date(blockStart).toISOString(),
        end_time: new Date(blockEnd).toISOString(),
        reason: blockReason,
      });
      setBlockOpen(false);
      setBlockReason("");
      loadCalendarData();
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    }
  };

  const saveMiniappChatId = async () => {
    setMiniChatSaving(true);
    setError("");
    try {
      await api.patch("/auth/me/miniapp-chat", {
        miniapp_chat_id: miniChatDraft.trim() ? miniChatDraft.trim() : null,
      });
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    } finally {
      setMiniChatSaving(false);
    }
  };

  const cancelAppointment = async (id) => {
    setError("");
    try {
      await api.patch(`/bookings/appointments/${id}/cancel`);
      setDetailApp(null);
      loadCalendarData();
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    }
  };

  const dayKeyOrder = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
  const dayLabels = {
    monday: "Пн",
    tuesday: "Вт",
    wednesday: "Ср",
    thursday: "Чт",
    friday: "Пт",
    saturday: "Сб",
    sunday: "Вс",
  };

  if (!user) return null;
  if (!canAccess) {
    return <Navigate to="/" replace />;
  }

  const chartData = (stats?.completed_by_day || []).map((x) => ({
    day: x.day,
    count: x.count,
  }));
  const popularHourData = (stats?.popular_hours || []).map((x) => ({
    hour: `${x.hour}:00`,
    count: x.count,
  }));

  return (
    <div className={PAGE_SHELL}>
      <header className="mb-6 flex flex-wrap items-center gap-3">
        <CalendarDays className="h-8 w-8 text-emerald-400" strokeWidth={1.5} aria-hidden />
        <h1 className="text-2xl font-semibold text-white">Записи</h1>
      </header>

      {user?.organization_id ? (
        <div className="mb-6 max-w-2xl rounded-lg border border-slate-600 bg-slate-900/50 p-4">
          <h2 className="mb-1 text-sm font-medium text-slate-200">Mini App (MAX): ваш chat_id</h2>
          
          <div className="flex flex-wrap items-end gap-2">
            <label className="min-w-[200px] flex-1">
              
              <input
                type="text"
                value={miniChatDraft}
                onChange={(e) => setMiniChatDraft(e.target.value)}
                maxLength={64}
                placeholder="например, из отладки Web App"
                className="w-full rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-white"
              />
            </label>
            <button
              type="button"
              disabled={miniChatSaving}
              onClick={saveMiniappChatId}
              className={BTN_SAVE_COMPACT}
            >
              <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
              {miniChatSaving ? "Сохранение…" : "Сохранить"}
            </button>
          </div>
        </div>
      ) : null}

      <div className={TAB_ROW}>
        {[
          { id: "calendar", label: "Календарь" },
          { id: "settings", label: "Настройки записи" },
          { id: "analytics", label: "Аналитика" },
        ].map((x) => (
          <button
            key={x.id}
            type="button"
            onClick={() => setTab(x.id)}
            className={tabBtn(tab === x.id)}
          >
            {x.label}
          </button>
        ))}
      </div>

      {error ? (
        <div className="mb-4 rounded border border-red-800 bg-red-950/40 px-3 py-2 text-sm text-red-200">{error}</div>
      ) : null}

      {tab === "calendar" ? (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {["day", "week", "month"].map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setCalView(v)}
                className={`rounded px-3 py-1.5 text-xs uppercase ${
                  calView === v ? "bg-slate-600 text-white" : "bg-slate-800 text-slate-400"
                }`}
              >
                {v === "day" ? "День" : v === "week" ? "Неделя" : "Месяц"}
              </button>
            ))}
            <button
              type="button"
              onClick={() => {
                const base = selectedDate;
                const s = new Date(base);
                s.setHours(9, 0, 0, 0);
                const e = new Date(base);
                e.setHours(10, 0, 0, 0);
                setBlockStart(s.toISOString().slice(0, 16));
                setBlockEnd(e.toISOString().slice(0, 16));
                setBlockOpen(true);
              }}
              className="ml-auto rounded bg-amber-700/80 px-3 py-1.5 text-xs text-white hover:bg-amber-600"
            >
              Заблокировать время
            </button>
          </div>

          {calView === "month" ? (
            <div className="flex flex-col gap-4 lg:flex-row">
              <div className="booking-cal-wrap max-w-md rounded-lg border border-slate-700 bg-slate-900/50 p-2">
                <Calendar
                  value={selectedDate}
                  onChange={(d) => d && setSelectedDate(d instanceof Date ? d : new Date(d))}
                  locale="ru-RU"
                />
              </div>
              <div className="min-h-[200px] flex-1 rounded-lg border border-slate-700 bg-slate-900/30 p-4">
                <h3 className="mb-2 text-sm font-medium text-slate-200">
                  {toYmd(selectedDate)} — записи и блокировки
                </h3>
                {loading ? (
                  <p className={PAGE_TEXT}>Загрузка…</p>
                ) : (
                  <ul className="space-y-2 text-sm">
                    {appointments
                      .filter((a) => toYmd(new Date(a.start_time)) === toYmd(selectedDate))
                      .map((a) => (
                        <li key={a.id}>
                          <button
                            type="button"
                            className="w-full rounded border border-slate-600 bg-slate-800/80 px-2 py-1.5 text-left text-slate-200 hover:border-emerald-600"
                            onClick={() => setDetailApp(a)}
                          >
                            <span className="text-emerald-400">{formatDateTimeRu(a.start_time)}</span> —{" "}
                            {(a.client_info?.name || a.client_info?.phone || "Клиент").toString()}
                          </button>
                        </li>
                      ))}
                    {busySlots
                      .filter((b) => toYmd(new Date(b.start_time)) === toYmd(selectedDate))
                      .map((b) => (
                        <li
                          key={b.id}
                          className="rounded border border-amber-900/60 bg-amber-950/30 px-2 py-1.5 text-amber-200"
                        >
                          Блок: {formatDateTimeRu(b.start_time)} — {formatDateTimeRu(b.end_time)}{" "}
                          {b.reason ? `(${b.reason})` : ""}
                        </li>
                      ))}
                  </ul>
                )}
              </div>
            </div>
          ) : null}

          {calView === "week" ? (
            <div className="overflow-x-auto rounded-lg border border-slate-700">
              <div className="grid min-w-[700px] grid-cols-7 gap-px bg-slate-800">
                {Array.from({ length: 7 }, (_, i) => {
                  const ws = startOfWeek(selectedDate);
                  const d = addDays(ws, i);
                  const ymd = toYmd(d);
                  const dayApps = appointments.filter((a) => toYmd(new Date(a.start_time)) === ymd);
                  const dayBusy = busySlots.filter((b) => toYmd(new Date(b.start_time)) === ymd);
                  return (
                    <div key={ymd} className="min-h-[220px] bg-slate-900/80 p-2">
                      <div className="mb-2 text-center text-xs font-medium text-slate-400">
                        {d.toLocaleDateString("ru-RU", { weekday: "short", day: "numeric", month: "numeric" })}
                      </div>
                      <div className="space-y-1 text-[11px]">
                        {dayBusy.map((b) => (
                          <div key={b.id} className="rounded bg-amber-900/40 px-1 py-0.5 text-amber-200">
                            Блок
                          </div>
                        ))}
                        {dayApps.map((a) => (
                          <button
                            key={a.id}
                            type="button"
                            className="block w-full rounded bg-emerald-900/40 px-1 py-0.5 text-left text-emerald-200"
                            onClick={() => setDetailApp(a)}
                          >
                            {new Date(a.start_time).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="flex justify-center gap-2 p-2">
                <button
                  type="button"
                  className="rounded bg-slate-700 px-2 py-1 text-xs text-white"
                  onClick={() => setSelectedDate(addDays(selectedDate, -7))}
                >
                  ← неделя
                </button>
                <button
                  type="button"
                  className="rounded bg-slate-700 px-2 py-1 text-xs text-white"
                  onClick={() => setSelectedDate(addDays(selectedDate, 7))}
                >
                  неделя →
                </button>
              </div>
            </div>
          ) : null}

          {calView === "day" ? (
            <div className="rounded-lg border border-slate-700 p-4">
              <div className="mb-3 flex items-center gap-2">
                <button
                  type="button"
                  className="rounded bg-slate-700 px-2 py-1 text-xs"
                  onClick={() => setSelectedDate(addDays(selectedDate, -1))}
                >
                  ←
                </button>
                <span className="text-slate-200">{toYmd(selectedDate)}</span>
                <button
                  type="button"
                  className="rounded bg-slate-700 px-2 py-1 text-xs"
                  onClick={() => setSelectedDate(addDays(selectedDate, 1))}
                >
                  →
                </button>
              </div>
              <div className="grid grid-cols-[48px_1fr] gap-1 text-xs">
                {Array.from({ length: 14 }, (_, h) => {
                  const hour = 8 + h;
                  const slotDate = new Date(selectedDate);
                  slotDate.setHours(hour, 0, 0, 0);
                  const slotEnd = new Date(slotDate);
                  slotEnd.setHours(hour + 1, 0, 0, 0);
                  const hit = appointments.find((a) => {
                    const st = new Date(a.start_time);
                    return st >= slotDate && st < slotEnd;
                  });
                  const bus = busySlots.find((b) => {
                    const st = new Date(b.start_time);
                    return st < slotEnd && new Date(b.end_time) > slotDate;
                  });
                  return (
                    <div key={hour} className="contents">
                      <div className="text-right text-slate-500">{pad2(hour)}:00</div>
                      <div
                        className={`min-h-[36px] rounded border px-2 py-1 ${
                          bus
                            ? "border-amber-700 bg-amber-950/40"
                            : hit
                              ? "border-emerald-700 bg-emerald-950/40"
                              : "border-slate-700 bg-slate-800/40"
                        }`}
                      >
                        {hit ? (
                          <button type="button" className="text-left text-emerald-200" onClick={() => setDetailApp(hit)}>
                            Запись
                          </button>
                        ) : bus ? (
                          <span className="text-amber-200">Занято</span>
                        ) : (
                          <button
                            type="button"
                            className="text-slate-500 hover:text-slate-300"
                            onClick={() => {
                              setBlockStart(slotDate.toISOString().slice(0, 16));
                              setBlockEnd(new Date(slotDate.getTime() + 60 * 60 * 1000).toISOString().slice(0, 16));
                              setBlockOpen(true);
                            }}
                          >
                            + блок
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}

          {blockOpen ? (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
              <div className="w-full max-w-md rounded-lg border border-slate-600 bg-slate-900 p-4 shadow-xl">
                <h3 className="mb-3 text-lg font-medium text-white">Блокировка времени</h3>
                <label className="mb-2 block text-xs text-slate-400">Начало</label>
                <input
                  type="datetime-local"
                  value={blockStart}
                  onChange={(e) => setBlockStart(e.target.value)}
                  className="mb-3 w-full rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-white"
                />
                <label className="mb-2 block text-xs text-slate-400">Конец</label>
                <input
                  type="datetime-local"
                  value={blockEnd}
                  onChange={(e) => setBlockEnd(e.target.value)}
                  className="mb-3 w-full rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-white"
                />
                <label className="mb-2 block text-xs text-slate-400">Причина</label>
                <input
                  type="text"
                  value={blockReason}
                  onChange={(e) => setBlockReason(e.target.value)}
                  className="mb-4 w-full rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-white"
                />
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    className="rounded px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
                    onClick={() => setBlockOpen(false)}
                  >
                    Отмена
                  </button>
                  <button
                    type="button"
                    className={BTN_SAVE_COMPACT}
                    onClick={submitBlock}
                  >
                    <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
                    Сохранить
                  </button>
                </div>
              </div>
            </div>
          ) : null}

          {detailApp ? (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
              <div className="w-full max-w-lg rounded-lg border border-slate-600 bg-slate-900 p-4 shadow-xl">
                <h3 className="mb-2 text-lg font-medium text-white">Запись</h3>
                <pre className="mb-4 max-h-60 overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-300">
                  {JSON.stringify(detailApp.client_info || {}, null, 2)}
                </pre>
                <p className="mb-4 text-sm text-slate-400">
                  {formatDateTimeRu(detailApp.start_time)} — {formatDateTimeRu(detailApp.end_time)}
                </p>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    className="rounded px-3 py-1.5 text-sm text-slate-300"
                    onClick={() => setDetailApp(null)}
                  >
                    Закрыть
                  </button>
                  {detailApp.status !== "canceled" ? (
                    <button
                      type="button"
                      className="rounded bg-red-800 px-3 py-1.5 text-sm text-white hover:bg-red-700"
                      onClick={() => cancelAppointment(detailApp.id)}
                    >
                      Отменить
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {tab === "settings" ? (
        <div className="max-w-xl space-y-4">
          {cfgLoading ? (
            <p className={PAGE_TEXT}>Загрузка…</p>
          ) : (
            <>
              <p className={`${PAGE_TEXT} mb-2`}>Рабочие часы (начало и конец дня, формат ЧЧ:ММ).</p>
              <div className="space-y-2">
                {dayKeyOrder.map((k) => (
                  <div key={k} className="flex flex-wrap items-center gap-2">
                    <span className="w-8 text-sm text-slate-400">{dayLabels[k]}</span>
                    <input
                      type="text"
                      placeholder="09:00"
                      value={Array.isArray(cfgWh[k]) ? cfgWh[k][0] || "" : ""}
                      onChange={(e) => {
                        const v = e.target.value;
                        setCfgWh((prev) => ({
                          ...prev,
                          [k]: [v, Array.isArray(prev[k]) ? prev[k][1] || "18:00" : "18:00"],
                        }));
                      }}
                      className="w-24 rounded border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-white"
                    />
                    <span className="text-slate-500">—</span>
                    <input
                      type="text"
                      placeholder="18:00"
                      value={Array.isArray(cfgWh[k]) ? cfgWh[k][1] || "" : ""}
                      onChange={(e) => {
                        const v = e.target.value;
                        setCfgWh((prev) => ({
                          ...prev,
                          [k]: [Array.isArray(prev[k]) ? prev[k][0] || "09:00" : "09:00", v],
                        }));
                      }}
                      className="w-24 rounded border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-white"
                    />
                  </div>
                ))}
              </div>
              <div className="mt-4">
                <label className="mb-1 block text-sm text-slate-400">Длительность приёма (мин)</label>
                <input
                  type="number"
                  min={5}
                  max={480}
                  step={5}
                  value={cfgDur}
                  onChange={(e) => setCfgDur(Number(e.target.value) || 30)}
                  className="w-32 rounded border border-slate-600 bg-slate-800 px-2 py-1.5 text-sm text-white"
                />
              </div>
              <button
                type="button"
                disabled={cfgSaving}
                onClick={saveConfig}
                className={`${BTN_SAVE} mt-4`}
              >
                <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
                {cfgSaving ? "Сохранение…" : "Сохранить"}
              </button>
            </>
          )}
        </div>
      ) : null}

      {tab === "analytics" ? (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <label className="flex items-center gap-2 text-sm text-slate-400">
              С
              <input
                type="date"
                value={statsFrom}
                onChange={(e) => setStatsFrom(e.target.value)}
                className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-white"
              />
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-400">
              По
              <input
                type="date"
                value={statsTo}
                onChange={(e) => setStatsTo(e.target.value)}
                className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-white"
              />
            </label>
            <button
              type="button"
              onClick={loadStats}
              className="rounded bg-slate-700 px-3 py-1 text-sm text-white"
            >
              Обновить
            </button>
          </div>
          {statsLoading ? (
            <p className={PAGE_TEXT}>Загрузка…</p>
          ) : stats ? (
            <div className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-4">
                  <div className="text-xs text-slate-500">Завершённых приёмов</div>
                  <div className="text-2xl font-semibold text-emerald-400">{stats.completed_consultations}</div>
                </div>
                <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-4">
                  <div className="text-xs text-slate-500">Выручка (указана в записях)</div>
                  <div className="text-2xl font-semibold text-white">{Number(stats.revenue_total).toFixed(2)}</div>
                </div>
                <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-4">
                  <div className="text-xs text-slate-500">По статусам</div>
                  <pre className="text-xs text-slate-300">{JSON.stringify(stats.counts_by_status, null, 2)}</pre>
                </div>
              </div>
              <div className="h-72 w-full rounded-lg border border-slate-700 bg-slate-900/30 p-4">
                <div className="mb-2 text-sm text-slate-400">Консультации по дням (завершённые)</div>
                <ResponsiveContainer width="100%" height="90%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="day" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fill: "#94a3b8", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
                      labelStyle={{ color: "#e2e8f0" }}
                    />
                    <Bar dataKey="count" fill="#10b981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="h-72 w-full rounded-lg border border-slate-700 bg-slate-900/30 p-4">
                <div className="mb-2 text-sm text-slate-400">Популярные часы (завершённые приёмы)</div>
                <ResponsiveContainer width="100%" height="90%">
                  <BarChart data={popularHourData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="hour" tick={{ fill: "#94a3b8", fontSize: 10 }} interval={0} angle={-35} height={60} />
                    <YAxis allowDecimals={false} tick={{ fill: "#94a3b8", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
                      labelStyle={{ color: "#e2e8f0" }}
                    />
                    <Bar dataKey="count" fill="#34d399" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
