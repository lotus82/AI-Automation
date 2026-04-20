import axios from "axios";
import { useCallback, useEffect, useState } from "react";
import { Typography } from "@maxhub/max-ui";
import { useMiniAppAuthStore } from "../../store/miniAppAuthStore.js";

function pad2(n) {
  return String(n).padStart(2, "0");
}

function toYmd(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function formatSlotLabel(iso) {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("ru-RU", {
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(iso);
  }
}

/**
 * Виджет записи на приём: свободные слоты сотрудника и фиксация в расписании (публичный API бронирования).
 *
 * @param {{ organizationId: string, staffUserId: string, introHtml?: string }} props
 */
export function MiniAppBookingContent({ organizationId, staffUserId, introHtml }) {
  const chatId = useMiniAppAuthStore((s) => s.chatId);
  const visitorName = useMiniAppAuthStore((s) => s.name);

  const [dateStr, setDateStr] = useState(() => toYmd(new Date()));
  const [slots, setSlots] = useState([]);
  const [durationMin, setDurationMin] = useState(30);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState((visitorName || "").trim());
  const [phone, setPhone] = useState("");
  const [picked, setPicked] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const loadSlots = useCallback(async () => {
    if (!organizationId || !staffUserId || !dateStr) return;
    setLoading(true);
    setError("");
    setPicked(null);
    setDone(false);
    try {
      const { data } = await axios.get(`/api/public/bookings/slots/${encodeURIComponent(staffUserId)}`, {
        params: {
          date: dateStr,
          organization_id: organizationId,
        },
      });
      setSlots(Array.isArray(data?.slots) ? data.slots : []);
      if (data?.appointment_duration != null) setDurationMin(Number(data.appointment_duration) || 30);
    } catch (e) {
      const d = e?.response?.data?.detail;
      setError(typeof d === "string" ? d : e?.message || "Не удалось загрузить слоты");
      setSlots([]);
    } finally {
      setLoading(false);
    }
  }, [organizationId, staffUserId, dateStr]);

  useEffect(() => {
    loadSlots();
  }, [loadSlots]);

  const onBook = async () => {
    if (!picked || !organizationId || !staffUserId) return;
    setSubmitting(true);
    setError("");
    try {
      await axios.post("/api/public/bookings/appointments", {
        staff_user_id: staffUserId,
        organization_id: organizationId,
        start_time: picked.start_time,
        end_time: picked.end_time,
        client_info: {
          name: (name || "").trim() || "Клиент",
          phone: (phone || "").trim(),
          max_chat_id: chatId != null && String(chatId).trim() !== "" ? String(chatId).trim() : undefined,
        },
      });
      setDone(true);
      setPicked(null);
      await loadSlots();
    } catch (e) {
      const d = e?.response?.data?.detail;
      setError(typeof d === "string" ? d : e?.message || "Не удалось записаться");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="miniapp-booking">
      {introHtml ? (
        <div
          className="miniapp-page-content mb-4"
          style={{ lineHeight: 1.55, fontSize: 15, color: "#1f2937" }}
          dangerouslySetInnerHTML={{ __html: introHtml }}
        />
      ) : null}

      <Typography.Body style={{ marginBottom: 8, color: "#374151" }}>
        Выберите дату и свободное время приёма.
      </Typography.Body>

      <div style={{ marginBottom: 12 }}>
        <label style={{ display: "block", fontSize: 12, color: "#6b7280", marginBottom: 4 }}>Дата</label>
        <input
          type="date"
          value={dateStr}
          onChange={(e) => setDateStr(e.target.value)}
          style={{
            width: "100%",
            maxWidth: 280,
            padding: "10px 12px",
            borderRadius: 10,
            border: "1px solid #d1d5db",
            fontSize: 16,
            color: "#111827",
          }}
        />
      </div>

      {durationMin ? (
        <p style={{ margin: "0 0 8px", fontSize: 12, color: "#6b7280" }}>Длительность приёма: {durationMin} мин.</p>
      ) : null}

      {error ? (
        <div
          style={{
            marginBottom: 12,
            padding: "10px 12px",
            borderRadius: 10,
            background: "#fef2f2",
            color: "#b91c1c",
            fontSize: 14,
          }}
        >
          {error}
        </div>
      ) : null}

      {done ? (
        <div
          style={{
            marginBottom: 12,
            padding: "12px 14px",
            borderRadius: 10,
            background: "#ecfdf5",
            color: "#047857",
            fontSize: 15,
          }}
        >
          Запись создана. Мы свяжемся с вами при необходимости.
        </div>
      ) : null}

      {loading ? (
        <Typography.Body style={{ color: "#6b7280" }}>Загрузка слотов…</Typography.Body>
      ) : slots.length === 0 ? (
        <Typography.Body style={{ color: "#6b7280" }}>
          На эту дату нет свободных окон. Выберите другую дату или обратитесь в организацию.
        </Typography.Body>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {slots.map((s, idx) => {
            const st = s.start_time;
            const en = s.end_time;
            const active =
              picked &&
              picked.start_time === st &&
              picked.end_time === en;
            return (
              <button
                key={`${st}-${en}-${idx}`}
                type="button"
                onClick={() => setPicked({ start_time: st, end_time: en })}
                style={{
                  textAlign: "left",
                  padding: "12px 14px",
                  borderRadius: 12,
                  border: active ? "2px solid var(--max-color-accent, #10b981)" : "1px solid #e5e7eb",
                  background: active ? "#ecfdf5" : "#fff",
                  color: "#111827",
                  fontSize: 15,
                  cursor: "pointer",
                }}
              >
                {formatSlotLabel(st)}
              </button>
            );
          })}
        </div>
      )}

      {picked && !done ? (
        <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid #e5e7eb" }}>
          <Typography.Body style={{ marginBottom: 8, fontWeight: 600 }}>Контакты для записи</Typography.Body>
          <label style={{ display: "block", fontSize: 12, color: "#6b7280", marginBottom: 4 }}>Имя</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Как к вам обращаться"
            style={{
              width: "100%",
              padding: "10px 12px",
              marginBottom: 10,
              borderRadius: 10,
              border: "1px solid #d1d5db",
              fontSize: 16,
            }}
          />
          <label style={{ display: "block", fontSize: 12, color: "#6b7280", marginBottom: 4 }}>Телефон</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+7 …"
            style={{
              width: "100%",
              padding: "10px 12px",
              marginBottom: 12,
              borderRadius: 10,
              border: "1px solid #d1d5db",
              fontSize: 16,
            }}
          />
          <button
            type="button"
            onClick={onBook}
            disabled={submitting}
            style={{
              width: "100%",
              padding: "12px 16px",
              borderRadius: 12,
              border: "none",
              background: "var(--max-color-accent, #10b981)",
              color: "#fff",
              fontSize: 16,
              fontWeight: 600,
              opacity: submitting ? 0.7 : 1,
            }}
          >
            {submitting ? "Отправка…" : "Записаться"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
