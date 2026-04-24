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
export const TAB_ROW =
  "mb-0 flex flex-nowrap gap-1 overflow-x-auto overscroll-x-contain border-b border-slate-600 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden";

export function tabBtn(active) {
  return `shrink-0 whitespace-nowrap rounded-t-lg border px-3 py-2 text-sm font-medium transition-colors sm:px-4 ${
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

/** Верхний блок страницы: заголовок и панель действий */
export const PAGE_HEAD =
  "mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between sm:gap-4";

export const PAGE_H1 = "text-2xl font-semibold tracking-tight text-slate-100";

/** Иконка рядом с текстом в кнопке */
export const ICON_BTN = "h-4 w-4 shrink-0";

/**
 * Единая синяя кнопка «Сохранить» (основной размер, как в настройках).
 * Используйте с иконкой Save из lucide-react.
 */
export const BTN_SAVE =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400/80 disabled:opacity-50 disabled:pointer-events-none";

/** Компактная синяя кнопка сохранения (модалки, второстепенные панели). */
export const BTN_SAVE_COMPACT =
  "inline-flex items-center justify-center gap-1.5 rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-sky-500 disabled:opacity-50";

/**
 * Кнопки с текстом «добавить» — с иконкой Plus.
 * Стили нейтральные (при необходимости обёрните в свой цвет).
 */
export const BTN_ADD =
  "inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-600 bg-slate-800 px-3 py-1.5 text-sm font-medium text-slate-200 shadow-sm hover:bg-slate-700 disabled:opacity-50";
