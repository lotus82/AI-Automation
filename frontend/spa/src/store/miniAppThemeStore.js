import { create } from "zustand";

/**
 * Тема публичного Mini App (мессенджер MAX).
 *
 * Значение `themeColor` задаётся админом в конструкторе сайтов и передаётся
 * в CSS-переменные дизайн-системы MAX UI внутри `MiniAppLayout`, чтобы акценты
 * (кнопки, ссылки) были в фирменном стиле организации, но в нативной форме.
 *
 * Отдельный стор (а не расширение `useMiniAppAuthStore`) сделан нарочно:
 *  - цвет живёт только на время сессии (persist не нужен — прилетит с бэкенда);
 *  - страницы публичного сайта могут обновлять тему без дергания авторизации.
 */
export const useMiniAppThemeStore = create((set) => ({
  /** Акцентный цвет в HEX (`#rrggbb` / `#rgb`). null — использовать дефолт дизайн-системы. */
  themeColor: null,
  /** Принудительная цветовая схема MAX UI: 'light' | 'dark' | null (автоопределение). */
  colorScheme: null,
  setThemeColor: (color) =>
    set({ themeColor: typeof color === "string" && color.trim() ? color.trim() : null }),
  setColorScheme: (scheme) =>
    set({ colorScheme: scheme === "light" || scheme === "dark" ? scheme : null }),
  reset: () => set({ themeColor: null, colorScheme: null }),
}));
