import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Хранилище JWT для публичного Mini App (мессенджер MAX).
 * Полностью независимо от `useAuthStore` (портальная авторизация):
 * пользователь Mini App — не сотрудник, у него своя сущность в БД.
 *
 * Ключ persist — свой, чтобы не пересекаться с хранилищем панели.
 */
export const useMiniAppAuthStore = create(
  persist(
    (set) => ({
      /** @type {string | null} JWT, typ=miniapp */
      token: null,
      /** Идентификаторы, связанные с токеном (дублируются в JWT, но удобны для UI). */
      userId: null,
      organizationId: null,
      chatId: null,
      name: null,
      organizationName: null,
      organizationDisplayName: null,
      setAuth: ({
        token,
        userId,
        organizationId,
        chatId,
        name,
        organizationName,
        organizationDisplayName,
      }) =>
        set({
          token: token ?? null,
          userId: userId ?? null,
          organizationId: organizationId ?? null,
          chatId: chatId ?? null,
          name: name ?? null,
          organizationName: organizationName ?? null,
          organizationDisplayName: organizationDisplayName ?? null,
        }),
      clearAuth: () =>
        set({
          token: null,
          userId: null,
          organizationId: null,
          chatId: null,
          name: null,
          organizationName: null,
          organizationDisplayName: null,
        }),
    }),
    {
      name: "lotus-miniapp-auth",
      partialize: (s) => ({
        token: s.token,
        userId: s.userId,
        organizationId: s.organizationId,
        chatId: s.chatId,
        name: s.name,
        organizationName: s.organizationName,
        organizationDisplayName: s.organizationDisplayName,
      }),
    }
  )
);
