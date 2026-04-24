import { Typography } from "@maxhub/max-ui";
import axios from "axios";
import { useCallback, useEffect, useState } from "react";
import { useMiniAppHtmlLinkDelegate } from "../../hooks/useMiniAppHtmlLinkDelegate.js";
import { openExternalLinkFromMiniApp } from "../../utils/miniAppOpenExternalLink.js";
import { PAGE_H1, PAGE_TEXT } from "../../styles/pageLayout.js";

/**
 * Страница сайта с ``page_kind=mis_patients``: список карточек пациентов врача (только при role=doctor).
 */
export function MiniAppMisPatientsContent({ miniToken, misRole, pageTitle, introHtml, themeColor }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const introRef = useMiniAppHtmlLinkDelegate(introHtml || "");

  const load = useCallback(async () => {
    if (!miniToken || misRole !== "doctor") {
      setRows([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setErr("");
    try {
      const { data } = await axios.get("/api/miniapp/mis/patients", {
        headers: { Authorization: `Bearer ${miniToken}` },
      });
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      const d = e?.response?.data?.detail;
      setErr(typeof d === "string" ? d : e?.message || "Ошибка загрузки");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [miniToken, misRole]);

  useEffect(() => {
    load();
  }, [load]);

  const openPatient = (id) => {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const url = `${origin}/public/mis/patient/${encodeURIComponent(String(id))}`;
    openExternalLinkFromMiniApp(url);
  };

  const accent = themeColor && String(themeColor).trim().startsWith("#") ? themeColor.trim() : "#0d9488";

  if (misRole !== "doctor") {
    return (
      <div style={{ padding: "24px 16px", textAlign: "center" }}>
        <h2
          style={{
            margin: "0 0 8px",
            fontSize: 20,
            fontWeight: 600,
            color: "#111827",
          }}
        >
          {(pageTitle || "").trim() || "Пациенты"}
        </h2>
        <Typography.Title style={{ fontSize: 17 }}>Только для врача</Typography.Title>
        <Typography.Body style={{ marginTop: 10, color: "#64748b", fontSize: 14 }}>
          Раздел «Пациенты» в Mini App доступен после указания вашего chat_id в панели: МИС → список пациентов → поле
          «Mini App (MAX): ваш chat_id».
        </Typography.Body>
      </div>
    );
  }

  return (
    <div style={{ padding: "12px 16px 24px" }}>
      <h2
        style={{
          margin: "0 0 12px",
          fontSize: 20,
          fontWeight: 600,
          lineHeight: 1.3,
          color: "#111827",
        }}
      >
        {(pageTitle || "").trim() || "Пациенты"}
      </h2>
      {introHtml && String(introHtml).trim() ? (
        <div
          ref={introRef}
          className="miniapp-page-content"
          style={{
            marginBottom: 16,
            lineHeight: 1.55,
            fontSize: 15,
            color: "#1f2937",
          }}
          dangerouslySetInnerHTML={{ __html: introHtml }}
        />
      ) : null}

      {loading ? (
        <div style={{ padding: 24, textAlign: "center", color: "#64748b" }}>Загрузка списка…</div>
      ) : err ? (
        <div style={{ padding: 16, borderRadius: 12, background: "#fef2f2", color: "#991b1b", fontSize: 14 }}>{err}</div>
      ) : rows.length === 0 ? (
        <div style={{ padding: 20, textAlign: "center", color: "#64748b", fontSize: 14 }}>
          Пока нет пациентов, закреплённых за вами.
        </div>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
          {rows.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => openPatient(p.id)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  padding: "14px 16px",
                  borderRadius: 14,
                  border: "1px solid #e2e8f0",
                  background: "#fff",
                  cursor: "pointer",
                  boxShadow: "0 1px 2px rgba(15,23,42,0.06)",
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 16, color: "#0f172a" }}>{p.full_name}</div>
                <div style={{ marginTop: 4, fontSize: 13, color: "#64748b" }}>Тел.: {p.phone || "—"}</div>
                <div style={{ marginTop: 8, fontSize: 12, color: accent }}>Открыть карту →</div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
