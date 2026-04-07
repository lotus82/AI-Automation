import { create } from "zustand";

/**
 * Параметры встраивания Битрикс24 (iframe): домен, APP_SID и др. из query при открытии placement.
 * Бэкенд FastAPI может ожидать их в заголовках — см. api/client.js.
 */
export const useBitrixAuthStore = create((set) => ({
  domain: null,
  appSid: null,
  /** Произвольные остальные query-параметры (AUTH_ID, PLACEMENT, …) */
  extra: {},

  setFromParsed: (payload) =>
    set({
      domain: payload.domain ?? null,
      appSid: payload.appSid ?? null,
      extra: payload.extra ?? {},
    }),

  reset: () =>
    set({
      domain: null,
      appSid: null,
      extra: {},
    }),
}));
