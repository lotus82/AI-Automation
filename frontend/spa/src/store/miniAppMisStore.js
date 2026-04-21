import { create } from "zustand";

/**
 * Роль МИС в Mini App (врач/пациент по chat_id) и опциональный JWT пациента после bootstrap.
 */
export const useMiniAppMisStore = create((set) => ({
  misRole: null,
  misSession: null,
  patientToken: null,
  setMisSession: (session) =>
    set({
      misSession: session || null,
      misRole: session?.role ?? null,
    }),
  setPatientToken: (token) => set({ patientToken: token || null }),
  reset: () => set({ misRole: null, misSession: null, patientToken: null }),
}));
