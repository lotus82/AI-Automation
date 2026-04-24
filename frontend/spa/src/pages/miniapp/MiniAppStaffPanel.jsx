import { Button, Flex, Spinner, Typography } from "@maxhub/max-ui";
import axios from "axios";
import { Save } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

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

function pad2(n) {
  return String(n).padStart(2, "0");
}

/** Начало календарного дня (локально) в мс */
function dayStartMs(d) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x.getTime();
}

/**
 * Запись в формате «дд.мм.гггг чч:мм - чч:мм» (локальное время браузера).
 */
function formatAppointmentRangeRu(isoStart, isoEnd) {
  const s = new Date(isoStart);
  const e = new Date(isoEnd);
  if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return "—";
  const dateStr = `${pad2(s.getDate())}.${pad2(s.getMonth() + 1)}.${s.getFullYear()}`;
  const t1 = `${pad2(s.getHours())}:${pad2(s.getMinutes())}`;
  const t2 = `${pad2(e.getHours())}:${pad2(e.getMinutes())}`;
  return `${dateStr} ${t1} - ${t2}`;
}

/** Единый стиль кнопок-действий (как «Позвонить»). */
const actionOutlineStyle = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "6px 12px",
  borderRadius: 8,
  border: "1px solid #d1d5db",
  background: "#fff",
  color: "#374151",
  fontSize: 13,
  fontWeight: 600,
  textDecoration: "none",
  cursor: "pointer",
  fontFamily: "inherit",
  boxSizing: "border-box",
};

function authHeaders(token) {
  const t = (token || "").trim();
  if (!t) return {};
  return { Authorization: `Bearer ${t}` };
}

/** Поля из client_info (публичная запись / Mini App). */
function parseClientInfo(ci) {
  const o = ci && typeof ci === "object" && !Array.isArray(ci) ? ci : {};
  const name = String(o.name ?? o.client_name ?? "").trim();
  const phone = String(o.phone ?? o.tel ?? "").trim();
  return {
    name: name || "Клиент",
    phone,
  };
}

function getMaxWebApp() {
  if (typeof window === "undefined") return null;
  return window.WebApp ?? window.MaxWebApp ?? window.maxWebApp ?? null;
}

/**
 * Диплинк «Отправить в MAX» с черновиком текста (см. dev.max.ru/help/deeplinks).
 * Пользователь выбирает чат — подходит для ответа клиенту, с которым есть переписка.
 */
function openMaxShareDraft(text) {
  const url = `https://max.ru/:share?text=${encodeURIComponent(text)}`;
  const bridge = getMaxWebApp();
  if (bridge?.openMaxLink) {
    bridge.openMaxLink(url);
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

/** Ссылка tel: для мобильного звонка. */
function telHref(phone) {
  const raw = String(phone || "").trim();
  if (!raw) return null;
  const d = raw.replace(/[\s()-]/g, "");
  if (!d) return null;
  if (d.startsWith("+")) return `tel:${d}`;
  if (/^8\d{10}$/.test(d)) return `tel:+7${d.slice(1)}`;
  if (/^7\d{10}$/.test(d)) return `tel:+${d}`;
  if (/^\d{10,15}$/.test(d)) return `tel:+${d}`;
  return `tel:${raw}`;
}

function appointmentShareDraft(a, clientName) {
  const range = formatAppointmentRangeRu(a.start_time, a.end_time);
  const hello =
    clientName && clientName !== "Клиент" ? `Здравствуйте, ${clientName}! ` : "Здравствуйте! ";
  return `${hello}По поводу записи: ${range}.`;
}

/**
 * Панель сотрудника в Mini App: записи к специалисту и настройки расписания (тот же API, что «Записи» в портале).
 */
export function MiniAppStaffPanel({ token }) {
  const headers = useMemo(() => authHeaders(token), [token]);
  const [tab, setTab] = useState("appointments");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [appointments, setAppointments] = useState([]);
  const [cfgWh, setCfgWh] = useState({});
  const [cfgDur, setCfgDur] = useState(30);
  const [cfgLoading, setCfgLoading] = useState(false);
  const [cfgSaving, setCfgSaving] = useState(false);

  const loadAppointments = useCallback(async () => {
    setError("");
    try {
      const { data } = await axios.get("/api/miniapp/staff/bookings/appointments", { headers });
      setAppointments(Array.isArray(data) ? data : []);
    } catch (e) {
      const d = e?.response?.data?.detail;
      setError(typeof d === "string" ? d : e?.message || "Ошибка загрузки записей");
    }
  }, [headers]);

  const loadConfig = useCallback(async () => {
    setCfgLoading(true);
    setError("");
    try {
      const { data } = await axios.get("/api/miniapp/staff/bookings/config", { headers });
      setCfgWh(data.working_hours && typeof data.working_hours === "object" ? data.working_hours : {});
      setCfgDur(Number(data.appointment_duration) || 30);
    } catch (e) {
      const d = e?.response?.data?.detail;
      setError(typeof d === "string" ? d : e?.message || "Ошибка загрузки настроек");
    } finally {
      setCfgLoading(false);
    }
  }, [headers]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      await Promise.all([loadAppointments(), loadConfig()]);
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [loadAppointments, loadConfig]);

  const saveConfig = async () => {
    setCfgSaving(true);
    setError("");
    try {
      await axios.put(
        "/api/miniapp/staff/bookings/config",
        { working_hours: cfgWh, appointment_duration: cfgDur },
        { headers },
      );
    } catch (e) {
      const d = e?.response?.data?.detail;
      setError(typeof d === "string" ? d : e?.message || "Ошибка сохранения");
    } finally {
      setCfgSaving(false);
    }
  };

  const cancelAppointment = async (id) => {
    setError("");
    try {
      await axios.patch(`/api/miniapp/staff/bookings/appointments/${id}/cancel`, null, { headers });
      await loadAppointments();
    } catch (e) {
      const d = e?.response?.data?.detail;
      setError(typeof d === "string" ? d : e?.message || "Ошибка отмены");
    }
  };

  const upcomingAppointments = useMemo(() => {
    const t0 = dayStartMs(new Date());
    return (appointments || [])
      .filter((a) => {
        const st = new Date(a.start_time);
        if (Number.isNaN(st.getTime())) return false;
        return dayStartMs(st) >= t0;
      })
      .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
  }, [appointments]);

  const archiveAppointments = useMemo(() => {
    const t0 = dayStartMs(new Date());
    return (appointments || [])
      .filter((a) => {
        const st = new Date(a.start_time);
        if (Number.isNaN(st.getTime())) return false;
        return dayStartMs(st) < t0;
      })
      .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
  }, [appointments]);

  if (!token) {
    return (
      <div style={{ padding: "24px 16px" }}>
        <Typography.Body>Нет токена авторизации.</Typography.Body>
      </div>
    );
  }

  if (loading) {
    return (
      <Flex direction="column" align="center" gap={12} style={{ padding: "48px 16px" }}>
        <Spinner size="large" />
        <Typography.Body>Загрузка…</Typography.Body>
      </Flex>
    );
  }

  return (
    <div style={{ padding: "16px 16px 24px" }}>
      <h2
        style={{
          margin: "0 0 12px",
          fontSize: 20,
          fontWeight: 600,
          lineHeight: 1.3,
          color: "#111827",
        }}
      >
        Управление
      </h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {[
          { id: "appointments", label: "Записи ко мне" },
          { id: "schedule", label: "Расписание" },
          { id: "archive", label: "Архив" },
        ].map((x) => (
          <button
            key={x.id}
            type="button"
            onClick={() => setTab(x.id)}
            style={{
              padding: "8px 14px",
              borderRadius: 10,
              border: tab === x.id ? "1.5px solid #4f46e5" : "1px solid #e5e7eb",
              background: tab === x.id ? "rgba(79,70,229,0.12)" : "#fff",
              color: tab === x.id ? "#4338ca" : "#374151",
              fontWeight: 600,
              fontSize: 14,
              cursor: "pointer",
            }}
          >
            {x.label}
          </button>
        ))}
      </div>

      {error ? (
        <div
          style={{
            marginBottom: 12,
            padding: "10px 12px",
            borderRadius: 10,
            background: "rgba(185, 28, 28, 0.08)",
            color: "#991b1b",
            fontSize: 14,
          }}
        >
          {error}
        </div>
      ) : null}

      {tab === "appointments" ? (
        <div>
          {upcomingAppointments.length === 0 ? (
            <Typography.Body style={{ color: "#6b7280" }}>
              Нет актуальных записей (сегодня и позже).
            </Typography.Body>
          ) : (
            <>
              <ul
                style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}
              >
                {upcomingAppointments.map((a) => {
                  const { name: clientName, phone } = parseClientInfo(a.client_info);
                  const tel = telHref(phone);
                  return (
                    <li
                      key={a.id}
                      style={{
                        border: "1px solid #e5e7eb",
                        borderRadius: 12,
                        padding: "12px 14px",
                        background: "#fafafa",
                      }}
                    >
                      <div style={{ fontSize: 14, fontWeight: 600, color: "#111827", marginBottom: 6 }}>
                        {formatAppointmentRangeRu(a.start_time, a.end_time)}
                      </div>
                      <div
                        style={{
                          fontSize: 14,
                          color: "#111827",
                          marginBottom: 6,
                          display: "flex",
                          flexDirection: "column",
                          gap: 4,
                        }}
                      >
                        <div>
                          <span style={{ color: "#6b7280", fontSize: 12 }}>Имя: </span>
                          {clientName}
                        </div>
                        <div>
                          <span style={{ color: "#6b7280", fontSize: 12 }}>Телефон: </span>
                          {phone ? phone : "—"}
                        </div>
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10, alignItems: "center" }}>
                        <button
                          type="button"
                          style={actionOutlineStyle}
                          onClick={() => openMaxShareDraft(appointmentShareDraft(a, clientName))}
                        >
                          ✍️ Написать
                        </button>
                        {tel ? (
                          <a href={tel} style={actionOutlineStyle}>
                            📞 Позвонить
                          </a>
                        ) : null}
                        {a.status !== "canceled" ? (
                          <button
                            type="button"
                            style={actionOutlineStyle}
                            onClick={() => cancelAppointment(a.id)}
                          >
                           ❌
                          </button>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>
      ) : null}

      {tab === "archive" ? (
        <div>
          {archiveAppointments.length === 0 ? (
            <Typography.Body style={{ color: "#6b7280" }}>В архиве пока пусто.</Typography.Body>
          ) : (
            <ul
              style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}
            >
              {archiveAppointments.map((a) => {
                const { name: clientName, phone } = parseClientInfo(a.client_info);
                const tel = telHref(phone);
                return (
                  <li
                    key={a.id}
                    style={{
                      border: "1px solid #e5e7eb",
                      borderRadius: 12,
                      padding: "12px 14px",
                      background: "#f9fafb",
                      opacity: 0.95,
                    }}
                  >
                    <div style={{ fontSize: 14, fontWeight: 600, color: "#111827", marginBottom: 6 }}>
                      {formatAppointmentRangeRu(a.start_time, a.end_time)}
                    </div>
                    <div
                      style={{
                        fontSize: 14,
                        color: "#111827",
                        marginBottom: 6,
                        display: "flex",
                        flexDirection: "column",
                        gap: 4,
                      }}
                    >
                      <div>
                        <span style={{ color: "#6b7280", fontSize: 12 }}>Имя: </span>
                        {clientName}
                      </div>
                      <div>
                        <span style={{ color: "#6b7280", fontSize: 12 }}>Телефон: </span>
                        {phone ? phone : "—"}
                      </div>
                      <div>
                        <span style={{ color: "#6b7280", fontSize: 12 }}>Статус: </span>
                        {a.status || "—"}
                      </div>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10, alignItems: "center" }}>
                      <button
                        type="button"
                        style={actionOutlineStyle}
                        onClick={() => openMaxShareDraft(appointmentShareDraft(a, clientName))}
                      >
                        Написать
                      </button>
                      {tel ? (
                        <a href={tel} style={actionOutlineStyle}>
                          Позвонить
                        </a>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}

      {tab === "schedule" ? (
        <div>
          {cfgLoading ? (
            <Typography.Body>Загрузка настроек…</Typography.Body>
          ) : (
            <>
              <Typography.Body style={{ marginBottom: 12, color: "#4b5563", fontSize: 14 }}>
                Рабочие часы (начало и конец дня, формат ЧЧ:ММ). Совпадает с разделом «Записи» в панели организации.
              </Typography.Body>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {dayKeyOrder.map((k) => (
                  <div key={k} style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
                    <span style={{ width: 28, fontSize: 14, color: "#6b7280" }}>{dayLabels[k]}</span>
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
                      style={{
                        width: 72,
                        padding: "6px 8px",
                        borderRadius: 8,
                        border: "1px solid #d1d5db",
                        fontSize: 14,
                      }}
                    />
                    <span style={{ color: "#9ca3af" }}>—</span>
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
                      style={{
                        width: 72,
                        padding: "6px 8px",
                        borderRadius: 8,
                        border: "1px solid #d1d5db",
                        fontSize: 14,
                      }}
                    />
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 16 }}>
                <label style={{ display: "block", fontSize: 14, color: "#6b7280", marginBottom: 6 }}>
                  Длительность приёма (мин)
                </label>
                <input
                  type="number"
                  min={5}
                  max={480}
                  step={5}
                  value={cfgDur}
                  onChange={(e) => setCfgDur(Number(e.target.value) || 30)}
                  style={{
                    width: 120,
                    padding: "8px 10px",
                    borderRadius: 8,
                    border: "1px solid #d1d5db",
                    fontSize: 14,
                  }}
                />
              </div>
              <div style={{ marginTop: 16 }}>
                <Button
                  mode="primary"
                  onClick={saveConfig}
                  disabled={cfgSaving}
                  style={{ background: "#0284c7", color: "#fff" }}
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <Save className="h-4 w-4" strokeWidth={2} aria-hidden />
                    {cfgSaving ? "Сохранение…" : "Сохранить расписание"}
                  </span>
                </Button>
              </div>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
