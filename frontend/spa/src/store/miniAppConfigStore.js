import { create } from "zustand";

/**
 * Конфигурация публичного Mini App (загружается с `GET /api/public/miniapp/config/{inn}`).
 *
 * Здесь живут:
 *  - идентификаторы и брендинг сайта (title/subtitle/logo/theme_color),
 *  - контакты (произвольный dict из JSONB),
 *  - список опубликованных страниц для нижней навигации (Tabbar).
 *
 * Persist не используется: конфиг дешевле перезагрузить, чем бороться с устаревшими
 * данными после правок в конструкторе сайтов.
 */
export const useMiniAppConfigStore = create((set) => ({
  /** @type {null | import('./miniAppConfigStore').MiniAppConfig} */
  config: null,
  loading: false,
  error: null,
  setLoading: (loading) => set({ loading: Boolean(loading) }),
  setError: (error) => set({ error: error ?? null }),
  setConfig: (config) =>
    set({
      config: config || null,
      error: null,
      loading: false,
    }),
  reset: () => set({ config: null, loading: false, error: null }),
}));
