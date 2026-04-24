import { Save } from "lucide-react";
import { AgentChat } from "../components/Chat/AgentChat.jsx";
import { VoiceTelephonyTestPanel } from "../components/telephony/VoiceTelephonyTestPanel.jsx";
import { BTN_SAVE, ICON_BTN } from "../styles/pageLayout.js";

const MAX_INTEGRATION_BASE_URL = "https://api.max.ru";
const MAX_PLATFORM_API_BASE_DEFAULT = "https://platform-api.max.ru";

const DEFAULT_MAX_GREETING = "Здравствуйте! Это ИИ-помощник компании. Слушаю вас.";

/**
 * Содержимое модалки встроенных интеграций (чаты, MAX, TG, VK, телефония).
 * state и обработчики передаёт родитель.
 */
export function IntegrationsSystemModalBody({
  systemModal,
  chatIntegrationIds,
  messengerLoadError,
  messengerLoading,
  maxForm,
  setMaxField,
  onMaxSubmit,
  maxSaving,
  maxStatusMsg,
  maxStatusError,
  telegramForm,
  setTelegramField,
  onTelegramSubmit,
  telegramSaving,
  telegramStatusMsg,
  telegramStatusError,
}) {
  if (systemModal === "chats") {
    return (
      <div className="w-full min-w-0 space-y-4 text-slate-200">
        <p className="m-0 text-sm text-slate-400">
          Потоковый ответ (SSE) с эндпоинта <code className="text-slate-300">POST /api/v1/chat/stream</code>. В запрос
          передаются идентификаторы интеграций из таблицы.
        </p>
        {chatIntegrationIds.length === 0 ? (
          <p className="m-0 rounded-lg border border-amber-900/40 bg-amber-950/20 px-3 py-2 text-sm text-amber-100/90">
            Нет интеграций с UUID в списке — чат откроется без инструментов. Создайте интеграцию через «Добавить».
          </p>
        ) : null}
        <div className="min-h-[12rem] min-w-0">
          <AgentChat integrationIds={chatIntegrationIds} />
        </div>
      </div>
    );
  }

  if (systemModal === "max") {
    return (
      <div className="w-full min-w-0 space-y-4 text-slate-200">
        {messengerLoadError ? (
          <p className="rounded-lg border border-red-900/40 bg-red-950/20 px-3 py-2 text-sm text-red-200/95">
            {messengerLoadError}
          </p>
        ) : null}
        <p
          className={`min-h-[1.25rem] text-sm ${maxStatusError ? "text-red-400" : "text-emerald-400"}`}
          aria-live="polite"
        >
          {maxStatusMsg}
        </p>
        {messengerLoading ? (
          <p className="text-slate-400">Загрузка…</p>
        ) : (
          <form
            className="space-y-4 rounded-xl border border-slate-700/80 bg-slate-800/40 p-5 shadow-sm"
            onSubmit={onMaxSubmit}
          >
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-200" htmlFor="int-max-base-url">
                base_url
              </label>
              <p className="text-sm text-slate-400">
                Базовый URL HTTP API бота (отправка сообщений, вызовы и т.д.) — тот же, что использует сервер. Изменение
                только через переменные окружения <code className="text-slate-300">MAX_API_BASE</code> /{" "}
                <code className="text-slate-300">MAX_PLATFORM_API_BASE</code> (по умолчанию:{" "}
                <code className="text-slate-300">{MAX_INTEGRATION_BASE_URL}</code> и{" "}
                <code className="text-slate-300">{MAX_PLATFORM_API_BASE_DEFAULT}</code> для long poll).
              </p>
              <input
                id="int-max-base-url"
                className="w-full cursor-default rounded-lg border border-slate-600 bg-slate-950/80 px-3 py-2 text-sm text-slate-300"
                type="url"
                readOnly
                autoComplete="off"
                name="max_base_url"
                value={MAX_INTEGRATION_BASE_URL}
                title="MAX Bot API: значение по умолчанию сервера"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-200" htmlFor="int-max-bot-username">
                Ник бота MAX (<code className="text-xs">@id…_bot</code>)
              </label>
              <p className="text-sm text-slate-400">
                Подстрока в тексте (например <code className="text-xs">@id…_bot</code>). В групповых чатах бот
                обрабатывает сообщение только при наличии этого упоминания.
              </p>
              <input
                id="int-max-bot-username"
                className="w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                type="text"
                autoComplete="off"
                placeholder="@id6451417302_bot"
                value={maxForm.maxBotUsername}
                onChange={(e) => setMaxField("maxBotUsername", e.target.value)}
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-200" htmlFor="int-max-bot-token">
                Токен бота MAX
              </label>
              <p className="text-sm text-slate-400">{maxForm.maxBotHint}</p>
              <input
                id="int-max-bot-token"
                className="w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                type="password"
                autoComplete="off"
                placeholder="Оставьте пустым, чтобы не менять сохранённый токен"
                value={maxForm.maxBotToken}
                onChange={(e) => setMaxField("maxBotToken", e.target.value)}
              />
            </div>

            <div>
              <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-200">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-500 bg-slate-900 accent-emerald-500"
                  checked={maxForm.maxUsePolling}
                  onChange={(e) => setMaxField("maxUsePolling", e.target.checked)}
                />
                Использовать Long Polling (для локальной отладки)
              </label>
              <p className="mt-1.5 text-sm text-slate-400">
                Опрос <code className="text-xs">GET /updates</code> у MAX без публичного HTTPS. В продакшене выключайте и
                используйте Webhook.
              </p>
            </div>

            <div>
              <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-200">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-500 bg-slate-900 accent-emerald-500"
                  checked={maxForm.maxVoiceReply}
                  onChange={(e) => setMaxField("maxVoiceReply", e.target.checked)}
                />
                Озвучивать ответы в MAX
              </label>
              <p className="mt-1.5 text-sm text-slate-400">
                После текстового ответа отправляется голосовое вложение. Нужен настроенный TTS.
              </p>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-200" htmlFor="int-max-call-delay">
                Задержка ответа на входящий звонок MAX, сек
              </label>
              <p className="text-sm text-slate-400">
                Сколько секунд ждать перед отправкой команды «принять вызов» в API MAX.
              </p>
              <input
                id="int-max-call-delay"
                className="w-full max-w-xs rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                type="number"
                min={0}
                max={120}
                step={1}
                value={maxForm.maxCallAnswerDelay}
                onChange={(e) => setMaxField("maxCallAnswerDelay", e.target.value)}
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-200" htmlFor="int-max-greeting">
                Приветствие при ответе на звонок MAX
              </label>
              <textarea
                id="int-max-greeting"
                className="w-full resize-y rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                rows={2}
                placeholder={DEFAULT_MAX_GREETING}
                value={maxForm.maxCallGreeting}
                onChange={(e) => setMaxField("maxCallGreeting", e.target.value)}
              />
            </div>

            <button type="submit" className={BTN_SAVE} disabled={maxSaving}>
              <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
              Сохранить настройки MAX
            </button>
          </form>
        )}
      </div>
    );
  }

  if (systemModal === "telegram") {
    return (
      <div className="w-full min-w-0 space-y-4 text-slate-200">
        {messengerLoadError ? (
          <p className="rounded-lg border border-red-900/40 bg-red-950/20 px-3 py-2 text-sm text-red-200/95">
            {messengerLoadError}
          </p>
        ) : null}
        <p
          className={`min-h-[1.25rem] text-sm ${telegramStatusError ? "text-red-400" : "text-emerald-400"}`}
          aria-live="polite"
        >
          {telegramStatusMsg}
        </p>
        {messengerLoading ? (
          <p className="text-slate-400">Загрузка…</p>
        ) : (
          <form
            className="space-y-4 rounded-xl border border-slate-700/80 bg-slate-800/40 p-5 shadow-sm"
            onSubmit={onTelegramSubmit}
          >
            <div>
              <label
                className="mb-1 flex items-center gap-1 text-sm font-medium text-slate-200"
                htmlFor="int-telegram-token"
              >
                <span className="text-sky-400" aria-hidden>
                  ✈
                </span>
                Токен Telegram-бота
              </label>
              <p className="text-sm text-slate-400">{telegramForm.telegramHint}</p>
              <input
                id="int-telegram-token"
                className="w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                type="password"
                autoComplete="off"
                placeholder="Оставьте пустым, чтобы не менять сохранённый токен"
                value={telegramForm.telegramToken}
                onChange={(e) => setTelegramField("telegramToken", e.target.value)}
              />
            </div>
            <button type="submit" className={BTN_SAVE} disabled={telegramSaving}>
              <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
              Сохранить токен
            </button>
          </form>
        )}
      </div>
    );
  }

  if (systemModal === "vk") {
    return (
      <div className="w-full min-w-0 space-y-4 text-slate-200">
        <p className="m-0 text-sm text-slate-400">
          Настройки сообщества и Callback API для ВКонтакте — позже появятся здесь (аналогично MAX и Telegram).
        </p>
        <div className="rounded-xl border border-slate-700/80 bg-slate-800/40 p-5 shadow-sm">
          <p className="m-0 text-sm text-slate-300">
            <span className="text-blue-400" aria-hidden>
              VK{" "}
            </span>
            Интеграция VK — <strong>в разработке</strong>. Секция зарезервирована под токены, подтверждение сервера и
            сценарии диалогов.
          </p>
        </div>
      </div>
    );
  }

  if (systemModal === "telephony") {
    return (
      <div className="w-full min-w-0 space-y-4 text-slate-200">
        <p className="m-0 text-sm text-slate-400">
          Проверка голосового потока через WebSocket (раньше отдельный раздел «Тестер»).
        </p>
        <VoiceTelephonyTestPanel />
      </div>
    );
  }

  return null;
}
