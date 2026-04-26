/** Единый вывод даты/времени: ДД.ММ.ГГГГ ЧЧ:ММ:СС в локальном времени браузера. */

function pad2(n) {
  return String(n).padStart(2, "0");
}

/** @param {string|number|Date|null|undefined} value */
export function parseToLocalDate(value) {
  if (value == null || value === "") return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value === "string") {
    const m = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (m) {
      const y = Number(m[1]);
      const mo = Number(m[2]);
      const d = Number(m[3]);
      return new Date(y, mo - 1, d, 0, 0, 0, 0);
    }
  }
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** @param {string|number|Date|null|undefined} value */
export function formatDateTimeRu(value) {
  const d = parseToLocalDate(value);
  if (!d) return "—";
  return `${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}.${d.getFullYear()} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

/** @param {string|number|Date|null|undefined} value */
export function formatDateRu(value) {
  const d = parseToLocalDate(value);
  if (!d) return "—";
  return `${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}.${d.getFullYear()}`;
}

/**
 * ``YYYY-MM-DD`` → ``ДД.ММ.ГГГГ`` (только дата, для полей ввода Mini App).
 * @param {string|null|undefined} isoYmd
 * @returns {string}
 */
export function isoYmdToRuDotted(isoYmd) {
  if (isoYmd == null || String(isoYmd).length < 10) return "";
  const s = String(isoYmd).slice(0, 10);
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return "";
  return `${m[3]}.${m[2]}.${m[1]}`;
}

/**
 * Разбор ``ДД.ММ.ГГГГ`` → ``YYYY-MM-DD`` или null при неверной дате/формате.
 * @param {string} ru
 * @returns {string|null}
 */
export function parseRuDottedToIsoYmd(ru) {
  const t = String(ru || "").trim();
  if (t === "") return null;
  const m = t.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  if (!m) return null;
  const d0 = parseInt(m[1], 10);
  const mo0 = parseInt(m[2], 10);
  const y0 = parseInt(m[3], 10);
  if (d0 < 1 || d0 > 31 || mo0 < 1 || mo0 > 12 || y0 < 1900 || y0 > 2100) return null;
  const d = new Date(y0, mo0 - 1, d0, 0, 0, 0, 0);
  if (d.getFullYear() !== y0 || d.getMonth() !== mo0 - 1 || d.getDate() !== d0) return null;
  return `${String(y0).padStart(4, "0")}-${String(mo0).padStart(2, "0")}-${String(d0).padStart(2, "0")}`;
}

/**
 * ``ДД.ММ.ГГГГ`` полностью валиден (и соответствует существующей дате).
 * @param {string} ru
 * @returns {boolean}
 */
export function isValidRuDottedDate(ru) {
  if (String(ru || "").trim() === "") return true;
  return parseRuDottedToIsoYmd(ru) != null;
}
