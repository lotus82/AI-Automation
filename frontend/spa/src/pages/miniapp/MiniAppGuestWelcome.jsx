import { Button, Flex, Typography } from "@maxhub/max-ui";
import axios from "axios";
import { useMemo, useState } from "react";
import { useMiniAppHtmlLinkDelegate } from "../../hooks/useMiniAppHtmlLinkDelegate.js";
import { useMiniAppConfigStore } from "../../store/miniAppConfigStore.js";
import { parseMisAgreementPageContent } from "../../utils/misAgreementPageContent.js";
import { MiniAppHeader } from "./MiniAppHeader.jsx";

const FALLBACK_AGREEMENT_HTML =
  "<p>Настройте страницу с типом «МИС: Пользовательское соглашение» в конструкторе сайта.</p>";

const agreementCardStyle = {
  borderRadius: 12,
  border: "1px solid rgba(15, 23, 42, 0.1)",
  overflow: "hidden",
  background: "#fff",
};

/**
 * Экран соглашения для гостя МИС: шапка как на остальных страницах, приветствие,
 * раскрывающееся соглашение на всю высоть под шапкой с кнопкой «Принять» внизу блока.
 */
export function MiniAppGuestWelcome({ miniToken, onAccepted, themeColor }) {
  const config = useMiniAppConfigStore((s) => s.config);
  const [isOpen, setIsOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState("");

  const agreementPage = useMemo(() => {
    const pages = Array.isArray(config?.pages) ? config.pages : [];
    return pages.find((p) => String(p?.page_kind || "").toLowerCase() === "mis_agreement") || null;
  }, [config?.pages]);

  const payload = useMemo(
    () =>
      parseMisAgreementPageContent(agreementPage?.content, {
        pageTitle: agreementPage?.title,
        siteTitle: config?.title,
        siteSubtitle: config?.subtitle,
      }),
    [agreementPage?.content, agreementPage?.title, config?.title, config?.subtitle],
  );

  const welcomeTitle =
    payload.welcome_title || (config?.title || "").trim() || "Добро пожаловать";
  const agreementTitle =
    payload.accordion_label ||
    (agreementPage?.title || "").trim() ||
    "Пользовательское соглашение";
  const agreementHtml = payload.agreement_html.trim() || FALLBACK_AGREEMENT_HTML;

  const welcomeHtmlRef = useMiniAppHtmlLinkDelegate(payload.welcome_html || "");
  const agreementRef = useMiniAppHtmlLinkDelegate(agreementHtml);
  const accent = (themeColor || "").trim() || "#2563eb";

  const onAccept = async () => {
    if (!isOpen || !miniToken) return;
    setErr("");
    setSubmitting(true);
    try {
      await axios.post(
        "/api/miniapp/mis/accept-agreement",
        {},
        { headers: { Authorization: `Bearer ${miniToken}` } },
      );
      onAccepted?.();
    } catch (e) {
      const d = e?.response?.data?.detail;
      setErr(typeof d === "string" ? d : d ? JSON.stringify(d) : e?.message || "Ошибка запроса");
    } finally {
      setSubmitting(false);
    }
  };

  const accordionToggle = (
    <button
      type="button"
      onClick={() => setIsOpen((v) => !v)}
      aria-expanded={isOpen}
      style={{
        width: "100%",
        textAlign: "left",
        padding: "14px 16px",
        border: "none",
        background: isOpen ? `${accent}14` : "#fafafa",
        cursor: "pointer",
        fontSize: 16,
        fontWeight: 600,
        color: "#1e293b",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        flexShrink: 0,
      }}
    >
      <span>{agreementTitle}</span>
      <span aria-hidden style={{ fontSize: 12, color: "#64748b" }}>
        {isOpen ? "▲" : "▼"}
      </span>
    </button>
  );

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
        width: "100%",
        background: "#ffffff",
        color: "#111827",
        overflow: "hidden",
      }}
    >
      <MiniAppHeader
        title={config?.title}
        subtitle={config?.subtitle}
        logoUrl={config?.logo_url}
        themeColor={themeColor}
        logoIconKey={config?.contacts?.mis_logo_icon}
      />

      {isOpen ? (
        <div
          style={{
            flex: 1,
            minHeight: 0,
            display: "flex",
            flexDirection: "column",
            padding: "0 16px max(16px, env(safe-area-inset-bottom, 0px))",
            boxSizing: "border-box",
          }}
        >
          <div
            style={{
              ...agreementCardStyle,
              flex: 1,
              minHeight: 0,
              display: "flex",
              flexDirection: "column",
            }}
          >
            {accordionToggle}
            <div
              style={{
                flex: 1,
                minHeight: 0,
                display: "flex",
                flexDirection: "column",
                padding: "0 16px 16px",
                boxSizing: "border-box",
              }}
            >
              <div
                ref={agreementRef}
                className="miniapp-page-content"
                style={{
                  flex: 1,
                  minHeight: 0,
                  overflowY: "auto",
                  WebkitOverflowScrolling: "touch",
                  lineHeight: 1.55,
                  fontSize: 15,
                  color: "#1f2937",
                  marginBottom: 12,
                }}
                dangerouslySetInnerHTML={{ __html: agreementHtml }}
              />
              <Button
                mode="primary"
                disabled={submitting}
                onClick={onAccept}
                style={{
                  width: "100%",
                  minHeight: 48,
                  fontSize: 16,
                  fontWeight: 600,
                  flexShrink: 0,
                }}
              >
                {submitting ? "Сохранение…" : "Принять"}
              </Button>
            </div>
          </div>
          {err ? (
            <Typography.Body style={{ color: "#b91c1c", margin: "12px 0 0", fontSize: 13 }}>
              {err}
            </Typography.Body>
          ) : null}
        </div>
      ) : (
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            WebkitOverflowScrolling: "touch",
            padding: "16px 16px max(24px, env(safe-area-inset-bottom, 0px))",
            boxSizing: "border-box",
          }}
        >
          <Flex direction="column" gap={20} align="stretch">
            <div>
              <h1
                style={{
                  margin: "0 0 10px",
                  fontSize: 22,
                  fontWeight: 700,
                  lineHeight: 1.25,
                  color: "#111827",
                }}
              >
                {welcomeTitle}
              </h1>
              {payload.welcome_html ? (
                <div
                  ref={welcomeHtmlRef}
                  className="miniapp-page-content"
                  style={{ lineHeight: 1.55, fontSize: 15, color: "#374151" }}
                  dangerouslySetInnerHTML={{ __html: payload.welcome_html }}
                />
              ) : null}
            </div>

            <div style={agreementCardStyle}>{accordionToggle}</div>

            {err ? (
              <Typography.Body style={{ color: "#b91c1c", margin: 0 }}>{err}</Typography.Body>
            ) : null}

            <Typography.Body style={{ color: "#64748b", fontSize: 13, margin: 0 }}>
              Разверните блок соглашения, ознакомьтесь с текстом и нажмите «Принять».
            </Typography.Body>
          </Flex>
        </div>
      )}
    </div>
  );
}
