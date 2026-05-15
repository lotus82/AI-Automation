/** Контент страницы ``mis_agreement``: JSON в поле ``content`` (без миграции БД). */

const SPLIT_MARKER = "<!--mis_agreement_split-->";

/**
 * @typedef {{
 *   welcome_title: string;
 *   welcome_html: string;
 *   accordion_label: string;
 *   agreement_html: string;
 * }} MisAgreementPagePayload
 */

/** @returns {MisAgreementPagePayload} */
export function emptyMisAgreementPayload(overrides = {}) {
  return {
    welcome_title: "",
    welcome_html: "",
    accordion_label: "Пользовательское соглашение",
    agreement_html: "",
    ...overrides,
  };
}

/**
 * @param {string | null | undefined} raw
 * @param {{ pageTitle?: string; siteTitle?: string; siteSubtitle?: string }} [fallback]
 * @returns {MisAgreementPagePayload}
 */
export function parseMisAgreementPageContent(raw, fallback = {}) {
  const s = (raw || "").trim();
  if (s.startsWith("{")) {
    try {
      const j = JSON.parse(s);
      if (j && typeof j === "object") {
        return emptyMisAgreementPayload({
          welcome_title: String(j.welcome_title ?? j.welcomeTitle ?? "").trim(),
          welcome_html: String(j.welcome_html ?? j.welcomeHtml ?? "").trim(),
          accordion_label: String(
            j.accordion_label ?? j.accordionLabel ?? fallback.pageTitle ?? "",
          ).trim(),
          agreement_html: String(j.agreement_html ?? j.agreementHtml ?? "").trim(),
        });
      }
    } catch {
      /* legacy HTML */
    }
  }
  if (s.includes(SPLIT_MARKER)) {
    const [intro = "", agreement = ""] = s.split(SPLIT_MARKER);
    return emptyMisAgreementPayload({
      welcome_html: intro.trim(),
      agreement_html: agreement.trim(),
      accordion_label: (fallback.pageTitle || "").trim(),
      welcome_title: (fallback.siteTitle || "").trim(),
    });
  }
  return emptyMisAgreementPayload({
    welcome_title: (fallback.siteTitle || "").trim(),
    welcome_html: (fallback.siteSubtitle || "").trim()
      ? `<p>${escapeHtml(fallback.siteSubtitle)}</p>`
      : "",
    accordion_label: (fallback.pageTitle || "Пользовательское соглашение").trim(),
    agreement_html: s,
  });
}

/** @param {MisAgreementPagePayload} payload */
export function serializeMisAgreementPageContent(payload) {
  const p = emptyMisAgreementPayload(payload);
  return JSON.stringify({
    welcome_title: p.welcome_title,
    welcome_html: p.welcome_html,
    accordion_label: p.accordion_label,
    agreement_html: p.agreement_html,
  });
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
