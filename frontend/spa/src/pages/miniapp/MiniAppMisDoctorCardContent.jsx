import { Typography } from "@maxhub/max-ui";
import { useMiniAppHtmlLinkDelegate } from "../../hooks/useMiniAppHtmlLinkDelegate.js";

/**
 * Страница «Карта пациента» для врача в Mini App: вступительный HTML + подсказка.
 */
export function MiniAppMisDoctorCardContent({ pageTitle, introHtml, themeColor }) {
  const introRef = useMiniAppHtmlLinkDelegate(introHtml || "");
  const accent = themeColor && String(themeColor).trim().startsWith("#") ? themeColor.trim() : "#0d9488";

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
        {(pageTitle || "").trim() || "Карта пациента"}
      </h2>
      {introHtml && String(introHtml).trim() ? (
        <div
          ref={introRef}
          className="miniapp-page-content"
          style={{ marginBottom: 16, lineHeight: 1.55, fontSize: 15, color: "#1f2937" }}
          dangerouslySetInnerHTML={{ __html: introHtml }}
        />
      ) : null}
      <div
        style={{
          padding: 16,
          borderRadius: 14,
          border: `1px solid ${accent}44`,
          background: `${accent}10`,
          fontSize: 14,
          color: "#0f172a",
          lineHeight: 1.5,
        }}
      >
        <Typography.Body style={{ margin: 0 }}>
          Откройте нужного пациента в разделе <strong>«Пациенты»</strong> — карта откроется во внешнем браузере. Полный
          доступ к МИС есть в веб-панели организации.
        </Typography.Body>
      </div>
    </div>
  );
}
