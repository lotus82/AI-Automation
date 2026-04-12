import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * JWT и профиль портала. Токен сохраняется в localStorage; профиль подгружается через GET /auth/me.
 */
export const useAuthStore = create(
  persist(
    (set) => ({
      token: null,
      user: null,
      setToken: (token) => set({ token }),
      setUser: (user) => set({ user }),
      setAuth: (token, user) => set({ token, user }),
      clearAuth: () => set({ token: null, user: null }),
    }),
    {
      name: "sales-ai-portal-auth",
      partialize: (state) => ({ token: state.token }),
    }
  )
);
