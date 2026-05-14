import { Button, Flex, Panel, Typography } from "@maxhub/max-ui";
import axios from "axios";
import { useMemo, useState } from "react";
import { useMiniAppHtmlLinkDelegate } from "../../hooks/useMiniAppHtmlLinkDelegate.js";
import { useMiniAppConfigStore } from "../../store/miniAppConfigStore.js";

const FALLBACK_AGREEMENT_HTML =
  "<p>Настройте страницу с типом «МИС: Пользовательское соглашение» в конструкторе сайта и опубликуйте её в меню.</p>";

/**
 * Приветствие гостя МИС Mini App: краткое описание, аккордеон с соглашением и «Принять» после раскрытия.
 */
export function MiniAppGuestWelcome({ miniToken, onAccepted }) {
  const config = useMiniAppConfigStore((s) => s.config);
  const [isOpen, setIsOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState("");

  const agreementPage = useMemo(() => {
    const pages = Array.isArray(config?.pages) ? config.pages : [];
    return pages.find((p) => String(p?.page_kind || "").toLowerCase() === "mis_agreement") || null;
  }, [config?.pages]);

  const agreementHtml = (agreementPage?.content || "").trim()
    ? agreementPage.content
    : FALLBACK_AGREEMENT_HTML;
  const agreementTitle =
    (agreementPage?.title || "").trim() || "Пользовательское соглашение";
  const introLine =
    (config?.subtitle || "").trim() ||
    (agreementPage?.title || "").trim() ||
    "Добро пожаловать в приложение клиники.";

  const agreementRef = useMiniAppHtmlLinkDelegate(agreementHtml);

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

  return (
    <div style={{ padding: "16px 16px 24px", maxWidth: 560, margin: "0 auto" }}>
      <Panel mode="secondary" style={{ padding: 16 }}>
        <Flex direction="column" gap={16} align="stretch">
          <Typography.Title style={{ margin: 0, fontSize: 20 }}>
            {((config?.title || "").trim() || "МИС").slice(0, 200)}
          </Typography.Title>
          <Typography.Body style={{ color: "#374151", lineHeight: 1.5, margin: 0 }}>
            {introLine}
          </Typography.Body>

          <div
            style={{
              borderRadius: 12,
              border: "1px solid rgba(15, 23, 42, 0.12)",
              overflow: "hidden",
              background: "#fff",
            }}
          >
            <button
              type="button"
              onClick={() => setIsOpen((v) => !v)}
              aria-expanded={isOpen}
              style={{
                width: "100%",
                textAlign: "left",
                padding: "14px 16px",
                border: "none",
                background: isOpen ? "rgba(99, 102, 241, 0.08)" : "#f8fafc",
                cursor: "pointer",
                fontSize: 16,
                fontWeight: 600,
                color: "#1e293b",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
              }}
            >
              <span>{agreementTitle}</span>
              <span aria-hidden style={{ fontSize: 12, color: "#64748b" }}>
                {isOpen ? "▲" : "▼"}
              </span>
            </button>
            {isOpen ? (
              <div style={{ padding: "0 16px 16px" }}>
                <div
                  ref={agreementRef}
                  className="miniapp-page-content"
                  style={{
                    lineHeight: 1.55,
                    fontSize: 15,
                    color: "#1f2937",
                    maxHeight: "min(52vh, 420px)",
                    overflowY: "auto",
                    marginBottom: 16,
                  }}
                  dangerouslySetInnerHTML={{ __html: agreementHtml }}
                />
                <Button
                  mode="primary"
                  disabled={submitting}
                  onClick={onAccept}
                  style={{ width: "100%", minHeight: 48, fontSize: 16, fontWeight: 600 }}
                >
                  {submitting ? "Сохранение…" : "Принять"}
                </Button>
              </div>
            ) : null}
          </div>

          {err ? (
            <Typography.Body style={{ color: "#b91c1c", margin: 0 }}>{err}</Typography.Body>
          ) : null}

          {!isOpen ? (
            <Typography.Body style={{ color: "#64748b", fontSize: 13, margin: 0 }}>
              Разверните блок соглашения, ознакомьтесь с текстом и нажмите «Принять».
            </Typography.Body>
          ) : null}
        </Flex>
      </Panel>
    </div>
  );
}
