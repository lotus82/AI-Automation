import { useCallback, useEffect, useId, useState } from "react";
import api from "../../api/client.js";

/**
 * Сценарии тренажёра: POST/GET `/api/scenarios`.
 * @param {{ onScenariosChanged?: () => void }} props
 */
export function TrainerScenariosPanel({ onScenariosChanged }) {
  const formId = useId();

  const [title, setTitle] = useState("");
  const [clientPersonaPrompt, setClientPersonaPrompt] = useState("");
  const [objectionsToRaise, setObjectionsToRaise] = useState("");
  const [formMessage, setFormMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [scenarios, setScenarios] = useState([]);
  const [listState, setListState] = useState("loading");
  const [listError, setListError] = useState("");

  const loadList = useCallback(async () => {
    setListState("loading");
    setListError("");
    try {
      const { data } = await api.get("/scenarios");
      setScenarios(Array.isArray(data) ? data : []);
      setListState("ready");
    } catch (e) {
      const msg = e?.response?.data?.detail
        ? typeof e.response.data.detail === "string"
          ? e.response.data.detail
          : JSON.stringify(e.response.data.detail)
        : e?.message || "Ошибка сети";
      setListError(String(msg));
      setListState("error");
      setScenarios([]);
    }
  }, []);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const body = {
      title: title.trim(),
      client_persona_prompt: clientPersonaPrompt.trim(),
      objections_to_raise: objectionsToRaise.trim(),
    };
    if (!body.title || !body.client_persona_prompt || !body.objections_to_raise) {
      setFormMessage("Заполните все обязательные поля.");
      return;
    }

    setSubmitting(true);
    setFormMessage("Отправка…");
    try {
      await api.post("/scenarios", body);
      setFormMessage("Сценарий сохранён.");
      setTitle("");
      setClientPersonaPrompt("");
      setObjectionsToRaise("");
      await loadList();
      onScenariosChanged?.();
    } catch (err) {
      const raw =
        err?.response?.data?.detail != null
          ? typeof err.response.data.detail === "string"
            ? err.response.data.detail
            : JSON.stringify(err.response.data.detail)
          : err?.response?.data != null
            ? JSON.stringify(err.response.data)
            : err?.message || "Ошибка";
      setFormMessage(`Ошибка: ${raw}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="w-full min-w-0 space-y-8 rounded-b-xl rounded-tr-xl border border-t-0 border-slate-600 bg-slate-800/30 p-5"
      role="tabpanel"
    >
      <div>
        <h2 className="flex items-center gap-2 text-xl font-semibold text-white">
          <span className="text-emerald-400" aria-hidden>
            ≡
          </span>
          Сценарии тренажёра
        </h2>
        <p className="mt-2 text-sm text-slate-400">
          РОП создаёт персону ИИ-клиента и список возражений. Менеджер отрабатывает их в голосовой симуляции на вкладке
          «Голосовая симуляция».
        </p>
      </div>

      <section>
        <h3 className="mb-3 text-lg font-semibold text-slate-200">Новый сценарий</h3>
        <form
          id={`${formId}-scenario-form`}
          className="w-full max-w-none space-y-4 rounded-2xl border border-slate-700/80 bg-slate-900/50 p-5 shadow-lg backdrop-blur-sm"
          onSubmit={(e) => void handleSubmit(e)}
        >
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400" htmlFor={`${formId}-title`}>
              Название
            </label>
            <input
              id={`${formId}-title`}
              name="title"
              required
              maxLength={512}
              placeholder="Кратко, для списка"
              className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-50"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={submitting}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400" htmlFor={`${formId}-persona`}>
              Персона клиента (системный промпт)
            </label>
            <textarea
              id={`${formId}-persona`}
              name="client_persona_prompt"
              required
              rows={6}
              placeholder="Кто клиент, тон, цели, ограничения…"
              className="min-h-32 w-full resize-y rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-50"
              value={clientPersonaPrompt}
              onChange={(e) => setClientPersonaPrompt(e.target.value)}
              disabled={submitting}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400" htmlFor={`${formId}-objections`}>
              Возражения и линии для отработки
            </label>
            <textarea
              id={`${formId}-objections`}
              name="objections_to_raise"
              required
              rows={5}
              placeholder="По пунктам: сроки, цена, качество…"
              className="min-h-24 w-full resize-y rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-50"
              value={objectionsToRaise}
              onChange={(e) => setObjectionsToRaise(e.target.value)}
              disabled={submitting}
            />
          </div>
          <div>
            <button
              type="submit"
              className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={submitting}
            >
              Сохранить
            </button>
          </div>
          {formMessage ? (
            <p
              className={`mt-2 text-sm ${
                formMessage.startsWith("Ошибка") ? "text-red-400" : "text-slate-400"
              }`}
              role="status"
            >
              {formMessage}
            </p>
          ) : null}
        </form>
      </section>

      <section>
        <h3 className="mb-3 text-lg font-semibold text-slate-200">Существующие сценарии</h3>
        {listState === "loading" && <p className="text-slate-500">Загрузка…</p>}
        {listState === "error" && (
          <p className="text-red-400">Ошибка загрузки: {listError || "неизвестно"}</p>
        )}
        {listState === "ready" && scenarios.length === 0 && (
          <p className="text-slate-500">Пока нет сценариев.</p>
        )}
        {listState === "ready" && scenarios.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2">
            {scenarios.map((it) => (
              <article
                key={String(it.id)}
                className="rounded-xl border border-slate-700/80 bg-slate-900/40 p-4 shadow-md"
              >
                <h4 className="text-base font-semibold text-white">{it.title}</h4>
                <p className="mt-2 break-all font-mono text-xs text-slate-500">
                  <code className="rounded bg-slate-950 px-1.5 py-0.5 text-emerald-300/90">{String(it.id)}</code>
                </p>
                {it.created_at != null && (
                  <p className="mt-2 text-xs text-slate-600">
                    Создан: {new Date(it.created_at).toLocaleString("ru-RU")}
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
