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
