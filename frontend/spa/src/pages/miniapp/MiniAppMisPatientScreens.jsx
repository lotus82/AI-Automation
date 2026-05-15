import { Typography } from "@maxhub/max-ui";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  ClipboardList,
  CreditCard,
  MessageCircle,
  Save,
  Settings,
  Trash2,
  User,
  Wallet,
} from "lucide-react";
import patientMisClient from "../../api/patientMisClient.js";
import { useMiniAppHtmlLinkDelegate } from "../../hooks/useMiniAppHtmlLinkDelegate.js";
import { BirthDateRuField } from "../../components/miniapp/BirthDateRuField.jsx";
import { useMiniAppConfigStore } from "../../store/miniAppConfigStore.js";
import { formatDateRu, formatDateTimeRu, isoYmdToRuDotted, parseRuDottedToIsoYmd } from "../../utils/dateTimeFormat.js";
import { openExternalLinkFromMiniApp } from "../../utils/miniAppOpenExternalLink.js";
import { clearPatientSession, getStoredPatientId } from "../../utils/patientMisAuth.js";
import { PAGE_H1, PAGE_TEXT } from "../../styles/pageLayout.js";

const KIND_TO_MODE = {
  mis_patient_card: "card",
  mis_patient_profile: "profile",
  mis_patient_diary: "diary",
  mis_patient_tips: "tips",
};

const profileCardStyle = {
  borderRadius: 14,
  border: "1px solid #e2e8f0",
  padding: 16,
  background: "#fff",
  marginBottom: 14,
};

function buildSupportHref(contacts) {
  const c = contacts || {};
  const tg = String(c.telegram || "").trim();
  if (tg) {
    if (tg.startsWith("http://") || tg.startsWith("https://")) return tg;
    const handle = tg.startsWith("@") ? tg.slice(1) : tg;
    return `https://t.me/${handle}`;
  }
  const email = String(c.email || "").trim();
  if (email) return `mailto:${email}`;
  const phone = String(c.phone || "").trim().replace(/\s/g, "");
  if (phone) return `tel:${phone}`;
  return null;
}

function profileActionBtnStyle(accent, variant = "default") {
  if (variant === "danger") {
    return {
      width: "100%",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      padding: "12px 14px",
      borderRadius: 12,
      border: "1px solid #fecaca",
      background: "#fef2f2",
      color: "#b91c1c",
      fontWeight: 600,
      fontSize: 14,
      cursor: "pointer",
    };
  }
  if (variant === "secondary") {
    return {
      width: "100%",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      padding: "12px 14px",
      borderRadius: 12,
      border: `1px solid ${accent}`,
      background: "#fff",
      color: accent,
      fontWeight: 600,
      fontSize: 14,
      cursor: "pointer",
    };
  }
  return {
    width: "100%",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    padding: "12px 14px",
    borderRadius: 12,
    border: "none",
    background: accent,
    color: "#fff",
    fontWeight: 600,
    fontSize: 14,
    cursor: "pointer",
  };
}

/**
 * Экраны пациента в Mini App МИС (разделы карты).
 */
export function MiniAppMisPatientScreens({ pageKind, pageTitle, introHtml, themeColor }) {
  const mode = KIND_TO_MODE[String(pageKind || "").toLowerCase()] || "card";
  const introRef = useMiniAppHtmlLinkDelegate(introHtml || "");
  const accent = themeColor && String(themeColor).trim().startsWith("#") ? themeColor.trim() : "#0d9488";
  const [patientId, setPatientId] = useState(() => getStoredPatientId() || "");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    setPatientId(getStoredPatientId() || "");
  }, []);

  const load = useCallback(async () => {
    const pid = getStoredPatientId();
    setPatientId(pid || "");
    if (!pid) {
      setData(null);
      setLoading(false);
      setErr("");
      return;
    }
    setLoading(true);
    setErr("");
    try {
      const res = await fetch(`/api/public/mis/patient/${encodeURIComponent(pid)}`);
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
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const patient = data?.patient;
  const entries = data?.entries ?? [];
  const recentExams = useMemo(
    () => entries.filter((e) => e.type === "exam").slice(0, 6),
    [entries],
  );

  const title =
    (pageTitle || "").trim() ||
    (mode === "card"
      ? "Карта"
      : mode === "profile"
        ? "Профиль"
        : mode === "diary"
          ? "Дневник здоровья"
          : "Полезные материалы");

  if (!patientId) {
    return (
      <div style={{ padding: "24px 16px", textAlign: "center" }}>
        <h2 style={{ margin: "0 0 8px", fontSize: 20, fontWeight: 600, color: "#111827" }}>{title}</h2>
        <Typography.Body style={{ color: "#64748b", fontSize: 14 }}>
          Нет привязки к карте пациента. Откройте мини-приложение из бота MAX после регистрации или привяжите chat_id в
          карте пациента.
        </Typography.Body>
      </div>
    );
  }

  if (loading && !data) {
    return (
      <div style={{ padding: 32, textAlign: "center", color: "#64748b" }}>
        <Typography.Body>Загрузка…</Typography.Body>
      </div>
    );
  }

  if (err) {
    return (
      <div style={{ padding: 16, margin: 16, borderRadius: 12, background: "#fef2f2", color: "#991b1b", fontSize: 14 }}>
        {err}
      </div>
    );
  }

  return (
    <div style={{ padding: "12px 16px 24px" }}>
      <h2
        style={{
          margin: "0 0 8px",
          fontSize: 20,
          fontWeight: 600,
          lineHeight: 1.3,
          color: "#111827",
        }}
      >
        {title}
      </h2>
      {introHtml && String(introHtml).trim() ? (
        <div
          ref={introRef}
          className="miniapp-page-content"
          style={{ marginBottom: 14, lineHeight: 1.55, fontSize: 15, color: "#1f2937" }}
          dangerouslySetInnerHTML={{ __html: introHtml }}
        />
      ) : null}

      {mode === "card" ? (
        <section style={{ borderRadius: 14, border: "1px solid #e2e8f0", padding: 16, background: "#fff" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <ClipboardList size={20} color={accent} aria-hidden />
            <span style={{ fontWeight: 600, fontSize: 16, color: "#0f172a" }}>Сводка</span>
          </div>
          <p style={{ margin: 0, fontSize: 15, color: "#334155" }}>
            <strong>{patient?.full_name || "—"}</strong>
          </p>
          <p style={{ margin: "8px 0 0", fontSize: 13, color: "#64748b" }}>
            Тел.: {patient?.phone || "—"} · Дата рождения: {formatDateRu(patient?.birth_date)}
          </p>
          {recentExams.length > 0 ? (
            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#475569", marginBottom: 8 }}>Последние обследования</div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, color: "#334155" }}>
                {recentExams.slice(0, 3).map((e) => (
                  <li key={e.id} style={{ marginBottom: 4 }}>
                    {formatDateTimeRu(e.entry_date)}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p style={{ margin: "12px 0 0", fontSize: 13, color: "#94a3b8" }}>Обследований пока нет.</p>
          )}
        </section>
      ) : null}

      {mode === "profile" ? (
        <ProfileBlock patient={patient} accent={accent} onSaved={load} />
      ) : null}

      {mode === "diary" ? <DiaryBlock patientId={patientId} accent={accent} onSent={load} /> : null}

      {mode === "tips" ? (
        <section style={{ borderRadius: 14, border: "1px solid #e2e8f0", padding: 16, background: "#fff" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <BookOpen size={20} color={accent} aria-hidden />
            <span style={{ fontWeight: 600, fontSize: 16, color: "#0f172a" }}>Полезные материалы</span>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, color: "#334155", lineHeight: 1.6 }}>
            <li>Соблюдайте назначенный режим лечения.</li>
            <li>При ухудшении самочувствия обратитесь к врачу.</li>
            <li>
              Рекомендации Минздрава:{" "}
              <a href="https://www.rosminzdrav.ru/" target="_blank" rel="noopener noreferrer" style={{ color: accent }}>
                rosminzdrav.ru
              </a>
            </li>
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function ProfileBlock({ patient, accent, onSaved }) {
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [birthText, setBirthText] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!patient) return;
    setFullName(patient.full_name || "");
    setPhone(patient.phone || "");
    const raw = patient.birth_date;
    if (raw && String(raw).length >= 10) {
      setBirthText(isoYmdToRuDotted(String(raw).slice(0, 10)));
    } else {
      setBirthText("");
    }
  }, [patient]);

  const save = async (e) => {
    e.preventDefault();
    const t = String(birthText).trim();
    if (t) {
      const parsed = parseRuDottedToIsoYmd(t);
      if (!parsed) {
        setMsg("Неверный формат даты. Используйте ДД.ММ.ГГГГ (например, 15.03.1990).");
        return;
      }
    }
    setBusy(true);
    setMsg("");
    try {
      await patientMisClient.patch("/mis/patient-session/me", {
        full_name: fullName.trim(),
        phone: phone.trim() || null,
        birth_date: t ? parseRuDottedToIsoYmd(t) : null,
      });
      setMsg("Сохранено.");
      await onSaved();
    } catch (err) {
      const d = err?.response?.data?.detail;
      setMsg(typeof d === "string" ? d : err?.message || "Ошибка сохранения");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
    <section style={profileCardStyle}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <User size={20} color={accent} aria-hidden />
        <span style={{ fontWeight: 600, fontSize: 16, color: "#0f172a" }}>Мои данные</span>
      </div>
      <form onSubmit={save}>
        <label style={{ display: "block", fontSize: 12, color: "#64748b", marginBottom: 8 }}>
          ФИО
          <input
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            style={{
              marginTop: 4,
              width: "100%",
              boxSizing: "border-box",
              padding: "10px 12px",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              fontSize: 15,
            }}
          />
        </label>
        <label style={{ display: "block", fontSize: 12, color: "#64748b", marginBottom: 8 }}>
          Телефон
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            style={{
              marginTop: 4,
              width: "100%",
              boxSizing: "border-box",
              padding: "10px 12px",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              fontSize: 15,
            }}
          />
        </label>
        <div style={{ marginBottom: 12 }}>
          <span style={{ display: "block", fontSize: 12, color: "#64748b", marginBottom: 6 }}>Дата рождения</span>
          <BirthDateRuField
            value={birthText}
            onChange={setBirthText}
            accent={accent}
            disabled={busy}
            inputStyle={{
              padding: "10px 12px",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              fontSize: 15,
            }}
          />
        </div>
        {msg ? (
          <p style={{ margin: "0 0 8px", fontSize: 13, color: msg.includes("Сохранено") ? "#0f766e" : "#b91c1c" }}>{msg}</p>
        ) : null}
        <button
          type="submit"
          disabled={busy}
          style={{
            width: "100%",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            padding: "12px 16px",
            borderRadius: 12,
            border: "none",
            background: "#0284c7",
            color: "#fff",
            fontWeight: 600,
            fontSize: 15,
            opacity: busy ? 0.7 : 1,
          }}
        >
          <Save className="h-[18px] w-[18px] shrink-0" strokeWidth={2} aria-hidden />
          {busy ? "Сохранение…" : "Сохранить"}
        </button>
      </form>
    </section>
      <TariffBlock accent={accent} />
      <ManagementBlock accent={accent} />
    </>
  );
}

function TariffBlock({ accent }) {
  return (
    <section style={profileCardStyle}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <CreditCard size={20} color={accent} aria-hidden />
        <span style={{ fontWeight: 600, fontSize: 16, color: "#0f172a" }}>Тариф</span>
      </div>
      <p style={{ margin: "0 0 6px", fontSize: 14, color: "#64748b" }}>
        Тариф: <strong style={{ color: "#0f172a" }}>Базовый</strong>
      </p>
      <p style={{ margin: "0 0 14px", fontSize: 14, color: "#64748b" }}>
        Баланс: <strong style={{ color: "#0f172a" }}>0.00 ₽</strong>
      </p>
      <button type="button" style={profileActionBtnStyle(accent)} onClick={() => {}}>
        <Wallet className="h-[18px] w-[18px] shrink-0" strokeWidth={2} aria-hidden />
        Пополнить
      </button>
    </section>
  );
}

function ManagementBlock({ accent }) {
  const config = useMiniAppConfigStore((s) => s.config);
  const supportHref = buildSupportHref(config?.contacts);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const onSupport = () => {
    if (supportHref) openExternalLinkFromMiniApp(supportHref);
    else setMsg("Контакты поддержки не настроены в конструкторе сайта.");
  };

  const onDeleteProfile = async () => {
    if (
      !window.confirm(
        "Удалить ваш профиль и все связанные данные? Это действие нельзя отменить.",
      )
    ) {
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      await patientMisClient.delete("/mis/patient-session/me");
      clearPatientSession();
      window.location.reload();
    } catch (err) {
      const d = err?.response?.data?.detail;
      setMsg(typeof d === "string" ? d : err?.message || "Не удалось удалить профиль");
      setBusy(false);
    }
  };

  return (
    <section style={{ ...profileCardStyle, marginBottom: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <Settings size={20} color={accent} aria-hidden />
        <span style={{ fontWeight: 600, fontSize: 16, color: "#0f172a" }}>Управление</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <button type="button" style={profileActionBtnStyle(accent, "secondary")} onClick={onSupport} disabled={busy}>
          <MessageCircle className="h-[18px] w-[18px] shrink-0" strokeWidth={2} aria-hidden />
          Написать в поддержку
        </button>
        <button type="button" style={profileActionBtnStyle(accent, "danger")} onClick={onDeleteProfile} disabled={busy}>
          <Trash2 className="h-[18px] w-[18px] shrink-0" strokeWidth={2} aria-hidden />
          {busy ? "Удаление…" : "Удалить мой профиль"}
        </button>
      </div>
      {msg ? <p style={{ margin: "10px 0 0", fontSize: 13, color: "#b91c1c" }}>{msg}</p> : null}
    </section>
  );
}

function DiaryBlock({ patientId, accent, onSent }) {
  const [dDate, setDDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [metric, setMetric] = useState("");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    const m = metric.trim();
    const v = value.trim();
    if (!m || !v) {
      setMsg("Укажите показатель и значение.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      const res = await fetch(`/api/public/mis/patient/${encodeURIComponent(patientId)}/diary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entry_date: dDate, metric: m, value: v }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(typeof j?.detail === "string" ? j.detail : `Ошибка ${res.status}`);
      }
      setMetric("");
      setValue("");
      setMsg("Запись отправлена.");
      await onSent();
    } catch (err) {
      setMsg(err?.message ?? String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section style={{ borderRadius: 14, border: "1px solid #e2e8f0", padding: 16, background: "#fff" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <HeartPulse size={20} color={accent} aria-hidden />
        <span style={{ fontWeight: 600, fontSize: 16, color: "#0f172a" }}>Дневник здоровья</span>
      </div>
      <form onSubmit={submit}>
        <label style={{ display: "block", fontSize: 12, color: "#64748b", marginBottom: 8 }}>
          Дата
          <input
            type="date"
            required
            value={dDate}
            onChange={(e) => setDDate(e.target.value)}
            style={{
              marginTop: 4,
              width: "100%",
              boxSizing: "border-box",
              padding: "10px 12px",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              fontSize: 15,
            }}
          />
        </label>
        <label style={{ display: "block", fontSize: 12, color: "#64748b", marginBottom: 8 }}>
          Показатель
          <input
            value={metric}
            onChange={(e) => setMetric(e.target.value)}
            placeholder="Например: давление"
            style={{
              marginTop: 4,
              width: "100%",
              boxSizing: "border-box",
              padding: "10px 12px",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              fontSize: 15,
            }}
          />
        </label>
        <label style={{ display: "block", fontSize: 12, color: "#64748b", marginBottom: 12 }}>
          Значение
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Например: 120/80"
            style={{
              marginTop: 4,
              width: "100%",
              boxSizing: "border-box",
              padding: "10px 12px",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              fontSize: 15,
            }}
          />
        </label>
        {msg ? (
          <p style={{ margin: "0 0 8px", fontSize: 13, color: msg.includes("отправлена") ? "#0f766e" : "#b91c1c" }}>{msg}</p>
        ) : null}
        <button
          type="submit"
          disabled={busy}
          style={{
            width: "100%",
            padding: "12px 16px",
            borderRadius: 12,
            border: "none",
            background: accent,
            color: "#fff",
            fontWeight: 600,
            fontSize: 15,
            opacity: busy ? 0.7 : 1,
          }}
        >
          {busy ? "Отправка…" : "Отправить врачу"}
        </button>
      </form>
    </section>
  );
}
