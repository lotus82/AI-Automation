import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * JWT и профиль портала. Токен сохраняется в localStorage; профиль подгружается через GET /auth/me.
 * Для super_admin: ``settingsOrganizationId`` — контекст для /settings и /knowledge (query organization_id).
 */
export const useAuthStore = create(
  persist(
    (set) => ({
      token: null,
      user: null,
      /** @type {string | null} UUID выбранной организации (только смысл для super_admin) */
      settingsOrganizationId: null,
      setToken: (token) => set({ token }),
      setUser: (user) => set({ user }),
      setSettingsOrganizationId: (settingsOrganizationId) => set({ settingsOrganizationId }),
      setAuth: (token, user) =>
        set((state) => ({
          token,
          user,
          settingsOrganizationId: user?.organization_id ?? state.settingsOrganizationId ?? null,
        })),
      clearAuth: () => set({ token: null, user: null, settingsOrganizationId: null }),
    }),
    {
      name: "sales-ai-portal-auth",
      partialize: (state) => ({
        token: state.token,
        settingsOrganizationId: state.settingsOrganizationId,
      }),
    }
  )
);
