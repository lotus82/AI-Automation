/**
 * Общая ширина и стили табов для разделов панели (в т.ч. «Сценарии» и вложенные страницы).
 * Редактируйте этот файл, чтобы поменять ширину контента и внешний вид вкладок.
 */

/** Единая максимальная ширина контента панели (как у раздела «Сценарии»). Задаётся в `Layout.jsx`. */
export const PAGE_SHELL = "w-full max-w-[100rem] min-w-0";

/** Внутренний блок страницы без повторного ограничения ширины (оболочка уже в Layout). */
export const PAGE_INNER = "w-full min-w-0";

export const PAGE_TEXT = "text-slate-100";

/** Строка табов (нижняя граница как у QA-аналитики). */
export const TAB_ROW = "mb-0 flex flex-wrap gap-1 border-b border-slate-600";

export function tabBtn(active) {
  return `rounded-t-lg border px-4 py-2 text-sm font-medium transition-colors ${
    active
      ? "border-slate-600 border-b-transparent bg-slate-800/90 text-white"
      : "border-transparent text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
  }`;
}

/** Подразделы маршрута `/scenarios/*` (права — по полю section). */
export const SCENARIOS_SUBSECTIONS = [
  { path: "qa-analytics", section: "qa-analytics", label: "QA-аналитика" },
  { path: "ai-trainer", section: "ai-trainer", label: "ИИ-тренер" },
  { path: "leadgen", section: "leadgen", label: "ИИ-лидогенератор" },
];

export function firstScenariosPathForUser(user, sectionsSet) {
  if (!user) return "qa-analytics";
  if (user.role === "super_admin" || user.role === "org_admin") return "qa-analytics";
  const hit = SCENARIOS_SUBSECTIONS.find((s) => sectionsSet.has(s.section));
  return hit ? hit.path : null;
}
