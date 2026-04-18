import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import QRCode from "react-qr-code";

const DEFAULT_HREF = "sberbankonline://sberbank.ru/qr/?uuid=2000175537";

function escapeHtmlAttr(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
    .replace(/</g, "&lt;");
}

/**
 * HTML-блок: SVG QR (react-qr-code) + ссылка. Одна и та же строка кодируется в QR и стоит в href — правьте в HTML при необходимости.
 *
 * @param {object} opts
 * @param {string} [opts.href] — полная ссылка, например sberbankonline://sberbank.ru/qr/?uuid=…
 */
export function buildSberQrDonationBlockHtml(opts = {}) {
  const hrefRaw = String(opts.href ?? DEFAULT_HREF).trim();
  const href = hrefRaw || DEFAULT_HREF;
  const size = 280;

  const svgMarkup = renderToStaticMarkup(
    createElement(QRCode, {
      value: href,
      size,
      level: "M",
      bgColor: "#ffffff",
      fgColor: "#000000",
    }),
  );

  const hrefEsc = escapeHtmlAttr(href);

  return `<div class="sber-donation-block" style="margin:24px 0;text-align:center;">
<a href="${hrefEsc}" rel="noopener noreferrer" style="display:inline-block;max-width:320px;text-decoration:none;-webkit-tap-highlight-color:transparent;">
<span style="display:block;width:100%;max-width:320px;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.12);overflow:hidden;line-height:0;background:#fff;">
${svgMarkup}
</span>
<span style="display:block;margin-top:14px;font-size:17px;font-weight:600;color:#21a038;font-family:system-ui,-apple-system,sans-serif;">Оплатить в Сбербанк Онлайн</span>
</a>
<p style="margin-top:12px;font-size:13px;color:#64748b;line-height:1.4;">Нажмите на QR-код. Ссылку можно изменить в HTML страницы.</p>
</div>`;
}

export { DEFAULT_HREF as SBER_DONATION_DEFAULT_HREF };
