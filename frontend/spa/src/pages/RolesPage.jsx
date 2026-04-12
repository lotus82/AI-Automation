import { useCallback, useEffect, useState } from "react";
import api from "../api/client.js";
import { SK } from "../constants/systemSettingsKeys.js";
import { mapFromList } from "../utils/systemSettingsForm.js";

function initialFormState() {
  return {
    consultantPrompt: "",
    maxGroupPrompt: "",
    textBotSupplement: "",
    analystPrompt: "",
  };
}

export function RolesPage() {
  const [form, setForm] = useState(initialFormState);
  const [statusMsg, setStatusMsg] = useState("");
  const [statusError, setStatusError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const applyMap = useCallback((map) => {
    setForm({
      consultantPrompt: map[SK.DEFAULT_CONSULTANT_PROMPT]?.value || "",
      maxGroupPrompt:
        map[SK.MAX_GROUP_ADDITIONAL_PROMPT]?.value != null
          ? String(map[SK.MAX_GROUP_ADDITIONAL_PROMPT].value)
          : "",
      textBotSupplement:
        map[SK.TEXT_BOT_SYSTEM_SUPPLEMENT]?.value != null
          ? String(map[SK.TEXT_BOT_SYSTEM_SUPPLEMENT].value)
          : "",
      analystPrompt: map[SK.ANALYST_QA_PROMPT]?.value || "",
    });
  }, []);

  const loadSettings = useCallback(async () => {
    setStatusMsg("Загрузка…");
    setStatusError(false);
    try {
      const { data: rows } = await api.get("/settings");
      applyMap(mapFromList(rows));
      setStatusMsg("Настройки загружены.");
      setStatusError(false);
    } catch (e) {
      console.error(e);
      const msg = e?.response?.data?.detail ?? e?.message ?? String(e);
      setStatusMsg(`Не удалось загрузить: ${msg}`);
      setStatusError(true);
    } finally {
      setLoading(false);
    }
  }, [applyMap]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const setField = (key, value) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  const collectPayload = () => ({
    [SK.DEFAULT_CONSULTANT_PROMPT]: form.consultantPrompt,
    [SK.MAX_GROUP_ADDITIONAL_PROMPT]: form.maxGroupPrompt,
    [SK.TEXT_BOT_SYSTEM_SUPPLEMENT]: form.textBotSupplement,
    [SK.ANALYST_QA_PROMPT]: form.analystPrompt,
  });

  const onSubmit = async (ev) => {
    ev.preventDefault();
    setSaving(true);
    setStatusMsg("Сохранение…");
    setStatusError(false);
    try {
      await api.put("/settings", { values: collectPayload() });
      setStatusMsg("Сохранено.");
      setStatusError(false);
      await loadSettings();
    } catch (e) {
      console.error(e);
      const body =
        typeof e?.response?.data === "string"
          ? e.response.data
          : e?.response?.data != null
            ? JSON.stringify(e.response.data)
            : e?.message ?? String(e);
      setStatusMsg(`Ошибка сохранения: ${body}`);
      setStatusError(true);
    } finally {
      setSaving(false);
    }
  };

  const inputClass =
    "w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500";
  const labelClass = "mb-1 block text-sm font-medium text-slate-200";
  const helpClass = "mt-0 text-sm text-slate-400";
  const sectionClass =
    "mb-8 rounded-xl border border-slate-700/80 bg-slate-800/40 p-5 shadow-sm";
  const sectionTitleClass =
    "mb-4 flex items-center gap-2 text-lg font-semibold text-slate-100";

  return (
    <div className="w-full min-w-0 text-slate-100">
      <h1 className="mb-2 flex items-center gap-2 text-2xl font-bold text-white">
        <span className="text-slate-300" aria-hidden>
          🎭
        </span>
        Роли и промпты
      </h1>
      <p className="mb-4 text-sm leading-relaxed text-slate-300">
        Системные промпты для консультанта, групповых чатов MAX, текстовых ботов и ОКК. Хранятся в БД (
        <code className="rounded bg-slate-800 px-1 text-xs">system_settings</code>).
      </p>

      <p
        className={`mb-4 min-h-[1.25rem] text-sm ${statusError ? "text-red-400" : "text-emerald-400"}`}
        aria-live="polite"
      >
        {statusMsg}
      </p>

      {loading ? (
        <p className="text-slate-400">Загрузка…</p>
      ) : (
        <form className="space-y-2" onSubmit={onSubmit}>
          <section className={sectionClass} aria-labelledby="roles-prompts-title">
            <h2 id="roles-prompts-title" className={sectionTitleClass}>
              <span aria-hidden>✏</span> Промпты
            </h2>

            <div className="mb-4">
              <label className={labelClass} htmlFor="consultant-prompt">
                Промпт консультанта (DEFAULT_CONSULTANT_PROMPT)
              </label>
              <textarea
                id="consultant-prompt"
                className={`${inputClass} resize-y`}
                rows={6}
                value={form.consultantPrompt}
                onChange={(e) => setField("consultantPrompt", e.target.value)}
              />
            </div>

            <div className="mb-4">
              <label className={labelClass} htmlFor="max-group-prompt">
                Дополнительный промпт для группы (MAX_GROUP_ADDITIONAL_PROMPT)
              </label>
              <p className={helpClass}>
                Вставляется в системное сообщение после основного промпта консультанта и инструкций по CRM, до
                дополнения для текстовых ботов.
              </p>
              <textarea
                id="max-group-prompt"
                className={`${inputClass} resize-y`}
                rows={3}
                value={form.maxGroupPrompt}
                onChange={(e) => setField("maxGroupPrompt", e.target.value)}
              />
            </div>

            <div className="mb-4">
              <label className={labelClass} htmlFor="text-bot-supplement">
                Дополнение для текстовых ботов MAX и Telegram (TEXT_BOT_SYSTEM_SUPPLEMENT)
              </label>
              <p className={helpClass}>
                Добавляется к системному промпту <strong>после</strong> основного промпта консультанта и инструкций по
                CRM. Используйте для правил формата ответа в мессенджере.
              </p>
              <textarea
                id="text-bot-supplement"
                className={`${inputClass} resize-y`}
                rows={5}
                placeholder='Например: Отвечай кратко, до 800 символов. Обращайся на «вы». Не используй Markdown.'
                value={form.textBotSupplement}
                onChange={(e) => setField("textBotSupplement", e.target.value)}
              />
            </div>

            <div className="mb-0">
              <label className={labelClass} htmlFor="analyst-prompt">
                Промпт ОКК (ANALYST_QA_PROMPT)
              </label>
              <textarea
                id="analyst-prompt"
                className={`${inputClass} resize-y`}
                rows={8}
                value={form.analystPrompt}
                onChange={(e) => setField("analystPrompt", e.target.value)}
              />
            </div>
          </section>

          <div className="mt-6">
            <button
              type="submit"
              className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-medium text-white shadow hover:bg-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 disabled:opacity-50"
              disabled={saving}
            >
              💾 Сохранить
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
