export function mapFromList(rows) {
  const m = {};
  (rows || []).forEach((r) => {
    m[r.key] = r;
  });
  return m;
}

export function hintForSecretRow(row) {
  if (!row) return "Ключ не задан.";
  const v = row.value;
  if (v == null || String(v).trim() === "") return "Ключ не задан.";
  if (String(v).includes("…")) return `Текущее значение (маска): ${row.value}`;
  return "Ключ задан.";
}

export function parseTruthy(value, defaultOnEmpty) {
  if (value == null || String(value).trim() === "") return defaultOnEmpty;
  const s = String(value).trim().toLowerCase();
  return s === "1" || s === "true" || s === "yes" || s === "on";
}

export function clampLlmTemp(n) {
  if (Number.isNaN(n)) return 0.2;
  return Math.max(0, Math.min(1, Math.round(n * 10) / 10));
}
