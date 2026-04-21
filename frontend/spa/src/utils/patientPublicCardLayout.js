/** Ключи блоков публичной карты пациента (порядок задаётся в конструкторе МИС). */

export const PATIENT_PUBLIC_SECTION_KEYS = ["profile", "exams", "surveys", "diary", "tips"];

export const PATIENT_PUBLIC_SECTION_LABELS = {
  profile: "Мои данные",
  exams: "Обследования",
  surveys: "Опросники от врача",
  diary: "Дневник здоровья",
  tips: "Полезные материалы",
};

/**
 * Нормализует порядок секций из темы карты: только известные ключи, без дубликатов, остальные в конец по умолчанию.
 * @param {Record<string, unknown> | null | undefined} theme
 */
export function normalizePublicSectionOrder(theme) {
  const raw = theme?.public_section_order;
  const arr = Array.isArray(raw) ? raw.map((x) => String(x)) : [];
  const allowed = new Set(PATIENT_PUBLIC_SECTION_KEYS);
  const out = [];
  for (const x of arr) {
    if (allowed.has(x) && !out.includes(x)) out.push(x);
  }
  for (const k of PATIENT_PUBLIC_SECTION_KEYS) {
    if (!out.includes(k)) out.push(k);
  }
  return out;
}
