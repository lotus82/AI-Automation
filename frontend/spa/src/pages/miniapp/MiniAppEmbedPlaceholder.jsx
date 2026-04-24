import { Typography } from "@maxhub/max-ui";
import { PAGE_H1, PAGE_TEXT } from "../../styles/pageLayout.js";

/** Подписи к ключам модулей (согласовано с backend `MINIAPP_EMBED_MODULE_CHOICES`). */
const LABELS = {
  knowledge: "База знаний",
  roles: "Роли и промпты",
  questionnaires: "Опросники",
  forms: "Формы",
  shops: "Магазины",
  integrations: "Интеграции",
  schedule: "Расписание",
  bookings: "Записи",
  bots: "Боты и каналы",
  logs: "Логи",
  applications: "Приложения",
  sites: "Сайты",
  mis: "МИС",
  chats: "Чаты",
};

/**
 * Заглушка встроенного модуля платформы на странице Mini App.
 * Реальные экраны подключаются позже по ключу `moduleKey`.
 */
export function MiniAppEmbedPlaceholder({ moduleKey }) {
  const k = typeof moduleKey === "string" ? moduleKey.trim() : "";
  if (!k) return null;
  const title = LABELS[k] || k;
  return (
    <div
      style={{
        marginBottom: 16,
        padding: "14px 16px",
        borderRadius: 12,
        border: "1px dashed rgba(79, 70, 229, 0.45)",
        background: "rgba(79, 70, 229, 0.06)",
      }}
    >
      <Typography.Title style={{ fontSize: 16, marginBottom: 6 }}>
        Модуль: {title}
      </Typography.Title>
      <Typography.Body style={{ fontSize: 14, color: "#4b5563", margin: 0 }}>
        Встроенный функционал платформы будет доступен здесь в следующих версиях. Пока отображается обычный
        контент страницы ниже.
      </Typography.Body>
    </div>
  );
}
