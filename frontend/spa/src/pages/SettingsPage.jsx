import { Save, Settings } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import api from "../api/client.js";
import { SK } from "../constants/systemSettingsKeys.js";
import {
  clampLlmTemp,
  hintForSecretRow,
  mapFromList,
  parseTruthy,
} from "../utils/systemSettingsForm.js";
import { BTN_SAVE, ICON_BTN, PAGE_H1, PAGE_HEADER, PAGE_TEXT, PAGE_TITLE_ICON } from "../styles/pageLayout.js";

function DeepSeekGlyph() {
  return (
    <svg
      className="mr-1 inline-block h-[1.25em] w-[1.25em] align-[-0.005em] text-inherit"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 30 30"
      fill="none"
      aria-hidden
    >
      <path
        d="M27.501 8.46875C27.249 8.3457 27.1406 8.58008 26.9932 8.69922C26.9434 8.73828 26.9004 8.78906 26.8584 8.83398C26.4902 9.22852 26.0605 9.48633 25.5 9.45508C24.6787 9.41016 23.9785 9.66797 23.3594 10.2969C23.2275 9.52148 22.79 9.05859 22.125 8.76172C21.7764 8.60742 21.4238 8.45312 21.1807 8.11719C21.0098 7.87891 20.9639 7.61328 20.8779 7.35156C20.8242 7.19336 20.7695 7.03125 20.5879 7.00391C20.3906 6.97266 20.3135 7.13867 20.2363 7.27734C19.9258 7.84375 19.8066 8.46875 19.8174 9.10156C19.8447 10.5234 20.4453 11.6562 21.6367 12.4629C21.7725 12.5547 21.8076 12.6484 21.7646 12.7832C21.6836 13.0605 21.5869 13.3301 21.501 13.6074C21.4473 13.7852 21.3662 13.8242 21.1768 13.7461C20.5225 13.4727 19.957 13.0684 19.458 12.5781C18.6104 11.7578 17.8438 10.8516 16.8877 10.1426C16.6631 9.97656 16.4395 9.82227 16.207 9.67578C15.2314 8.72656 16.335 7.94727 16.5898 7.85547C16.8574 7.75977 16.6826 7.42773 15.8193 7.43164C14.957 7.43555 14.167 7.72461 13.1611 8.10938C13.0137 8.16797 12.8594 8.21094 12.7002 8.24414C11.7871 8.07227 10.8389 8.0332 9.84766 8.14453C7.98242 8.35352 6.49219 9.23633 5.39648 10.7441C4.08105 12.5547 3.77148 14.6133 4.15039 16.7617C4.54883 19.0234 5.70215 20.8984 7.47559 22.3633C9.31348 23.8809 11.4307 24.625 13.8457 24.4824C15.3125 24.3984 16.9463 24.2012 18.7881 22.6406C19.2529 22.8711 19.7402 22.9629 20.5498 23.0332C21.1729 23.0918 21.7725 23.002 22.2373 22.9062C22.9648 22.752 22.9141 22.0781 22.6514 21.9531C20.5186 20.959 20.9863 21.3633 20.5605 21.0371C21.6445 19.752 23.2783 18.418 23.917 14.0977C23.9668 13.7539 23.9238 13.5391 23.917 13.2598C23.9131 13.0918 23.9512 13.0254 24.1445 13.0059C24.6787 12.9453 25.1973 12.7988 25.6738 12.5352C27.0557 11.7793 27.6123 10.5391 27.7441 9.05078C27.7637 8.82422 27.7402 8.58789 27.501 8.46875ZM15.46 21.8613C13.3926 20.2344 12.3906 19.6992 11.9766 19.7227C11.5898 19.7441 11.6592 20.1875 11.7441 20.4766C11.833 20.7617 11.9492 20.959 12.1123 21.209C12.2246 21.375 12.3018 21.623 12 21.8066C11.334 22.2207 10.1768 21.668 10.1221 21.6406C8.77539 20.8477 7.64941 19.7988 6.85547 18.3652C6.08984 16.9844 5.64453 15.5039 5.57129 13.9238C5.55176 13.541 5.66406 13.4062 6.04297 13.3379C6.54199 13.2461 7.05762 13.2266 7.55664 13.2988C9.66602 13.6074 11.4619 14.5527 12.9668 16.0469C13.8262 16.9004 14.4766 17.918 15.1465 18.9121C15.8584 19.9688 16.625 20.9746 17.6006 21.7988C17.9443 22.0879 18.2197 22.3086 18.4824 22.4707C17.6895 22.5586 16.3652 22.5781 15.46 21.8613ZM16.4502 15.4805C16.4502 15.3105 16.5859 15.1758 16.7568 15.1758C16.7949 15.1758 16.8301 15.1836 16.8613 15.1953C16.9033 15.2109 16.9424 15.2344 16.9727 15.2695C17.0273 15.3223 17.0586 15.4004 17.0586 15.4805C17.0586 15.6504 16.9229 15.7852 16.7529 15.7852C16.582 15.7852 16.4502 15.6504 16.4502 15.4805ZM19.5273 17.0625C19.3301 17.1426 19.1328 17.2129 18.9434 17.2207C18.6494 17.2344 18.3281 17.1152 18.1533 16.9688C17.8828 16.7422 17.6895 16.6152 17.6074 16.2168C17.5732 16.0469 17.5928 15.7852 17.623 15.6348C17.6934 15.3105 17.6152 15.1035 17.3877 14.9141C17.2012 14.7598 16.9658 14.7188 16.7061 14.7188C16.6094 14.7188 16.5205 14.6758 16.4541 14.6406C16.3457 14.5859 16.2568 14.4512 16.3418 14.2852C16.3691 14.2324 16.501 14.1016 16.5322 14.0781C16.8838 13.877 17.29 13.9434 17.666 14.0938C18.0146 14.2363 18.2773 14.498 18.6562 14.8672C19.0439 15.3145 19.1133 15.4395 19.334 15.7734C19.5078 16.0371 19.667 16.3066 19.7754 16.6152C19.8408 16.8066 19.7559 16.9648 19.5273 17.0625Z"
        fill="#4D6BFE"
        fillRule="nonzero"
      />
    </svg>
  );
}

const tabBtn = (active) =>
  `rounded-t-lg border px-4 py-2 text-sm font-medium transition-colors ${
    active
      ? "border-slate-600 border-b-transparent bg-slate-800/90 text-white"
      : "border-transparent text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
  }`;

function initialFormState() {
  return {
    llmProvider: "deepseek",
    llmTemp: 0.2,
    deepseekKey: "",
    openaiKey: "",
    salutespeechKey: "",
    hints: {
      deepseek: "",
      openai: "",
      salutespeech: "",
    },
    salutespeechScope: "",
    salutespeechVoice: "",
    maxContextLimit: "10",
    enableWebSearch: true,
  };
}

export function SettingsPage() {
  const [settingsTab, setSettingsTab] = useState("llm");
  const [form, setForm] = useState(initialFormState);
  const [statusMsg, setStatusMsg] = useState("");
  const [statusError, setStatusError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const applyMap = useCallback((map) => {
    let tv = 0.2;
    const lt = map[SK.LLM_TEMPERATURE];
    if (lt && lt.value != null && String(lt.value).trim() !== "") {
      const parsedT = parseFloat(String(lt.value).replace(",", "."));
      if (!Number.isNaN(parsedT)) tv = parsedT;
    }
    tv = clampLlmTemp(tv);

    const mxc = map[SK.MAX_CONTEXT_LIMIT];
    const ctx =
      mxc && mxc.value && String(mxc.value).trim() !== ""
        ? String(mxc.value).trim()
        : "10";

    setForm({
      ...initialFormState(),
      llmProvider: (map[SK.LLM_PROVIDER]?.value || "deepseek").toLowerCase(),
      llmTemp: tv,
      hints: {
        deepseek: hintForSecretRow(map[SK.DEEPSEEK_API_KEY]),
        openai: hintForSecretRow(map[SK.OPENAI_API_KEY]),
        salutespeech: hintForSecretRow(map[SK.SALUTESPEECH_AUTH_KEY]),
      },
      salutespeechScope: map[SK.SALUTESPEECH_SCOPE]?.value || "",
      salutespeechVoice: map[SK.SALUTESPEECH_VOICE]?.value || "",
      maxContextLimit: ctx,
      enableWebSearch: parseTruthy(map[SK.ENABLE_WEB_SEARCH]?.value, true),
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
      setStatusMsg(`Не удалось загрузить настройки: ${msg}`);
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

  const onLlmRangeInput = (e) => {
    const steps = parseInt(e.target.value, 10);
    const s = Number.isNaN(steps) ? 2 : steps;
    setField("llmTemp", clampLlmTemp(s / 10));
  };

  const onLlmNumberInput = (e) => {
    const v = parseFloat(e.target.value, 10);
    setField("llmTemp", clampLlmTemp(v));
  };

  const collectPayload = () => {
    const values = {};
    values[SK.LLM_PROVIDER] = form.llmProvider.trim();
    values[SK.LLM_TEMPERATURE] = String(form.llmTemp);
    values[SK.SALUTESPEECH_SCOPE] =
      form.salutespeechScope.trim() || "SALUTE_SPEECH_PERS";
    values[SK.SALUTESPEECH_VOICE] =
      form.salutespeechVoice.trim() || "Ost_24000";

    let lim = parseInt(form.maxContextLimit, 10);
    if (Number.isNaN(lim)) lim = 10;
    lim = Math.max(1, Math.min(200, lim));
    values[SK.MAX_CONTEXT_LIMIT] = String(lim);

    values[SK.ENABLE_WEB_SEARCH] = form.enableWebSearch ? "1" : "0";

    const secretPairs = [
      [SK.DEEPSEEK_API_KEY, form.deepseekKey],
      [SK.OPENAI_API_KEY, form.openaiKey],
      [SK.SALUTESPEECH_AUTH_KEY, form.salutespeechKey],
    ];
    secretPairs.forEach(([k, v]) => {
      if (v.trim()) values[k] = v.trim();
    });

    return values;
  };

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

  const llmRangeValue = Math.round(form.llmTemp * 10);
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
      <header className={PAGE_HEADER}>
        <Settings className={PAGE_TITLE_ICON} strokeWidth={1.5} aria-hidden />
        <h1 className={PAGE_H1}>Настройки системы</h1>
      </header>

      <p
        className={`mb-4 min-h-[1.25rem] text-sm ${statusError ? "text-red-400" : "text-emerald-400"}`}
        aria-live="polite"
      >
        {statusMsg}
      </p>

      {loading ? (
        <p className="text-slate-400">Загрузка формы…</p>
      ) : (
        <form className="space-y-2" onSubmit={onSubmit}>
          <div className="flex flex-wrap gap-1 border-b border-slate-700/80">
            <button type="button" className={tabBtn(settingsTab === "llm")} onClick={() => setSettingsTab("llm")}>
              LLM
            </button>
            <button type="button" className={tabBtn(settingsTab === "stt")} onClick={() => setSettingsTab("stt")}>
              STT
            </button>
            <button type="button" className={tabBtn(settingsTab === "tts")} onClick={() => setSettingsTab("tts")}>
              TTS
            </button>
          </div>

          {settingsTab === "llm" ? (
            <section className={sectionClass} aria-labelledby="settings-llm-title">
              <h2 id="settings-llm-title" className={sectionTitleClass}>
                <span aria-hidden>🧠</span> LLM
              </h2>

              <div className="mb-4">
                <label className={labelClass} htmlFor="llm-provider">
                  Провайдер LLM
                </label>
                <select
                  id="llm-provider"
                  name="LLM_PROVIDER"
                  className={inputClass}
                  value={form.llmProvider}
                  onChange={(e) => setField("llmProvider", e.target.value)}
                >
                  <option value="deepseek">DeepSeek</option>
                  <option value="openai">OpenAI</option>
                </select>
              </div>

              <div className="mb-4">
                <label className={labelClass} htmlFor="llm-temperature">
                  <span aria-hidden>🌡</span> Температура LLM
                </label>
                <div className="flex flex-wrap items-center gap-3">
                  <input
                    type="range"
                    id="llm-temperature-range"
                    min={0}
                    max={10}
                    step={1}
                    value={llmRangeValue}
                    onChange={onLlmRangeInput}
                    aria-label="Температура LLM ползунок"
                    className="min-w-[10rem] flex-1 accent-sky-500"
                  />
                  <input
                    className={`${inputClass} w-20 shrink-0`}
                    type="number"
                    id="llm-temperature"
                    name="LLM_TEMPERATURE"
                    min={0}
                    max={1}
                    step={0.1}
                    value={form.llmTemp}
                    onInput={onLlmNumberInput}
                    onChange={onLlmNumberInput}
                  />
                </div>
              </div>

              <div className="mb-4">
                <label className={`${labelClass} inline-flex items-center`} htmlFor="deepseek-key">
                  <DeepSeekGlyph />
                  Ключ DeepSeek API
                </label>
                <p className={helpClass}>{form.hints.deepseek}</p>
                <input
                  className={inputClass}
                  type="password"
                  id="deepseek-key"
                  autoComplete="off"
                  placeholder="Оставьте пустым, чтобы не менять сохранённый ключ"
                  value={form.deepseekKey}
                  onChange={(e) => setField("deepseekKey", e.target.value)}
                />
              </div>

              <div className="mb-4">
                <label className={labelClass} htmlFor="openai-key">
                  Ключ OpenAI API
                </label>
                <p className={helpClass}>{form.hints.openai}</p>
                <input
                  className={inputClass}
                  type="password"
                  id="openai-key"
                  autoComplete="off"
                  placeholder="Оставьте пустым, чтобы не менять сохранённый ключ"
                  value={form.openaiKey}
                  onChange={(e) => setField("openaiKey", e.target.value)}
                />
              </div>

              <div className="mb-4">
                <label className={labelClass} htmlFor="max-context-limit">
                  Лимит сообщений в контексте LLM
                </label>
                <p className={helpClass}>
                  Сколько последних реплик (user/assistant) подмешивать в запрос к модели
                </p>
                <input
                  className={inputClass}
                  type="number"
                  id="max-context-limit"
                  min={1}
                  max={200}
                  step={1}
                  value={form.maxContextLimit}
                  onChange={(e) => setField("maxContextLimit", e.target.value)}
                />
              </div>

              <div className="mb-0">
                <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-200">
                  <input
                    type="checkbox"
                    id="enable-web-search"
                    className="h-4 w-4 rounded border-slate-500 bg-slate-900 accent-sky-500"
                    checked={form.enableWebSearch}
                    onChange={(e) => setField("enableWebSearch", e.target.checked)}
                  />
                  Разрешить веб-поиск
                </label>
              </div>
            </section>
          ) : null}

          {settingsTab === "stt" ? (
            <section className={sectionClass} aria-labelledby="settings-stt-title">
              <h2 id="settings-stt-title" className={sectionTitleClass}>
                <span aria-hidden>🎤</span> STT (SaluteSpeech)
              </h2>
              
              <div className="mb-4">
                <label className={labelClass} htmlFor="salutespeech-key">
                  Ключ SaluteSpeech
                </label>
                <p className={helpClass}>{form.hints.salutespeech}</p>
                <input
                  className={inputClass}
                  type="password"
                  id="salutespeech-key"
                  name="SALUTESPEECH_AUTH_KEY"
                  autoComplete="off"
                  placeholder="Оставьте пустым, чтобы не менять сохранённый ключ"
                  value={form.salutespeechKey}
                  onChange={(e) => setField("salutespeechKey", e.target.value)}
                />
              </div>

              <div className="mb-0">
                <label className={labelClass} htmlFor="salutespeech-scope">
                  OAuth scope
                </label>
                <input
                  className={inputClass}
                  type="text"
                  id="salutespeech-scope"
                  autoComplete="off"
                  placeholder="SALUTE_SPEECH_PERS"
                  value={form.salutespeechScope}
                  onChange={(e) => setField("salutespeechScope", e.target.value)}
                />
              </div>
            </section>
          ) : null}

          {settingsTab === "tts" ? (
            <section className={sectionClass} aria-labelledby="settings-tts-title">
              <h2 id="settings-tts-title" className={sectionTitleClass}>
                <span aria-hidden>🔊</span> TTS (SaluteSpeech)
              </h2>
              
              <div className="mb-0">
                <label className={labelClass} htmlFor="salutespeech-voice">
                  Голос TTS
                </label>
                <input
                  className={inputClass}
                  type="text"
                  id="salutespeech-voice"
                  autoComplete="off"
                  placeholder="Ost_24000"
                  value={form.salutespeechVoice}
                  onChange={(e) => setField("salutespeechVoice", e.target.value)}
                />
              </div>
            </section>
          ) : null}

          <div className="mt-6">
            <button type="submit" className={BTN_SAVE} disabled={saving}>
              <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
              Сохранить
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
