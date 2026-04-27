import { Plus, RefreshCcw, Save, Settings } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import api from "../api/client.js";
import { SK } from "../constants/systemSettingsKeys.js";
import { PANEL_EXTRA_KIND } from "../constants/voiceProviderKinds.js";
import { IconDeleteButton } from "../components/ui/IconActionButtons.jsx";
import {
  BTN_ADD,
  BTN_SAVE,
  ICON_BTN,
  PAGE_H1,
  PAGE_HEADER_BETWEEN,
  PAGE_TEXT,
  PAGE_TITLE_ICON,
  tabBtn,
} from "../styles/pageLayout.js";
import {
  clampLlmTemp,
  hintForSecretRow,
  mapFromList,
  parseTruthy,
} from "../utils/systemSettingsForm.js";

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

const BTN_RELOAD_ICON =
  "inline-flex items-center justify-center rounded-lg border border-slate-600 bg-slate-800/70 p-2 text-slate-200 hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60 disabled:opacity-60";

function initialFormState() {
  return {
    llmProvider: "deepseek",
    llmModel: "deepseek-chat",
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

function emptyExtras() {
  return { llm: [], stt: [], tts: [] };
}

function newExtraId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    try {
      return crypto.randomUUID();
    } catch {
      /* ignore */
    }
  }
  return `x-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function normalizeExtraRow(r) {
  if (!r || typeof r !== "object") return null;
  const kind = r.kind || PANEL_EXTRA_KIND.NOTE;
  if (kind === PANEL_EXTRA_KIND.TBANK_VK_STT || kind === PANEL_EXTRA_KIND.TBANK_VK_TTS) {
    const c = r.config && typeof r.config === "object" ? r.config : {};
    return {
      ...r,
      kind,
      value: typeof r.value === "string" ? r.value : "",
      config: {
        api_key: String(c.api_key ?? ""),
        secret_key: String(c.secret_key ?? ""),
        endpoint: String(c.endpoint ?? ""),
      },
    };
  }
  return {
    ...r,
    kind: PANEL_EXTRA_KIND.NOTE,
    name: String(r.name ?? ""),
    value: typeof r.value === "string" ? r.value : "",
  };
}

function parseExtrasFromMap(map) {
  const raw = map[SK.PANEL_SETTINGS_EXTRAS]?.value;
  if (raw == null || String(raw).trim() === "") {
    return emptyExtras();
  }
  try {
    const o = JSON.parse(String(raw));
    if (!o || typeof o !== "object") return emptyExtras();
    const norm = (arr) => (Array.isArray(arr) ? arr.map((x) => normalizeExtraRow(x)).filter(Boolean) : []);
    return {
      llm: norm(o.llm),
      stt: norm(o.stt),
      tts: norm(o.tts),
    };
  } catch {
    return emptyExtras();
  }
}

export function SettingsPage() {
  const [settingsTab, setSettingsTab] = useState("llm");
  const [form, setForm] = useState(initialFormState);
  const [extras, setExtras] = useState(emptyExtras);
  const [statusMsg, setStatusMsg] = useState("");
  const [statusError, setStatusError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [addName, setAddName] = useState("");
  const [addValue, setAddValue] = useState("");
  /** ``note`` | ``voicekit`` — только для вкладок STT/TTS */
  const [sttTtsAddMode, setSttTtsAddMode] = useState("voicekit");
  const [vkApiKey, setVkApiKey] = useState("");
  const [vkSecretKey, setVkSecretKey] = useState("");
  const [vkEndpoint, setVkEndpoint] = useState("");
  const [llmModelOptions, setLlmModelOptions] = useState([]);
  const [llmModelsSource, setLlmModelsSource] = useState("");
  const [llmModelsLoading, setLlmModelsLoading] = useState(false);

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

    const prov = (map[SK.LLM_PROVIDER]?.value || "deepseek").toLowerCase();
    const fromDb = (map[SK.LLM_MODEL]?.value || "").trim();
    const defModel = prov === "openai" ? "gpt-4o-mini" : "deepseek-chat";
    const llmModel = fromDb || defModel;

    setForm({
      ...initialFormState(),
      llmProvider: prov,
      llmModel,
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
    setExtras(parseExtrasFromMap(map));
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

  const loadLlmModelList = useCallback(async () => {
    setLlmModelsLoading(true);
    try {
      const { data } = await api.get("/settings/llm-models", {
        params: { provider: form.llmProvider },
      });
      setLlmModelOptions(Array.isArray(data?.models) ? data.models : []);
      setLlmModelsSource(String(data?.source || ""));
    } catch (e) {
      console.error(e);
      setLlmModelOptions([]);
      setLlmModelsSource("fallback");
    } finally {
      setLlmModelsLoading(false);
    }
  }, [form.llmProvider]);

  useEffect(() => {
    if (settingsTab !== "llm") return;
    loadLlmModelList();
  }, [settingsTab, form.llmProvider, loadLlmModelList]);

  const setField = (key, value) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  const onLlmRangeInput = (e) => {
    const steps = parseInt(e.target.value, 10);
    const s = Number.isNaN(steps) ? 2 : steps;
    setField("llmTemp", clampLlmTemp(s / 10));
  };

  const onLlmNumberInput = (e) => {
    const v = parseFloat(e.target.value);
    setField("llmTemp", clampLlmTemp(Number.isNaN(v) ? 0.2 : v));
  };

  const collectPayload = () => {
    const values = {};
    values[SK.LLM_PROVIDER] = form.llmProvider.trim();
    values[SK.LLM_MODEL] = form.llmModel.trim();
    values[SK.LLM_TEMPERATURE] = String(form.llmTemp);
    values[SK.SALUTESPEECH_SCOPE] = form.salutespeechScope.trim() || "SALUTE_SPEECH_PERS";
    values[SK.SALUTESPEECH_VOICE] = form.salutespeechVoice.trim() || "Ost_24000";

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

    values[SK.PANEL_SETTINGS_EXTRAS] = JSON.stringify(extras);
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

  const openAddModal = () => {
    setAddName("");
    setAddValue("");
    setSttTtsAddMode("voicekit");
    setVkApiKey("");
    setVkSecretKey("");
    setVkEndpoint("");
    setAddModalOpen(true);
  };

  const closeAddModal = () => setAddModalOpen(false);

  const confirmAddModal = () => {
    const name = addName.trim();
    if (!name) {
      setStatusMsg("Укажите название записи.");
      setStatusError(true);
      return;
    }
    const tab = settingsTab;
    if (tab === "llm") {
      setExtras((x) => ({
        ...x,
        llm: [...x.llm, { id: newExtraId(), name, kind: PANEL_EXTRA_KIND.NOTE, value: addValue }],
      }));
    } else if (tab === "stt" || tab === "tts") {
      if (sttTtsAddMode === "note") {
        const row = { id: newExtraId(), name, kind: PANEL_EXTRA_KIND.NOTE, value: addValue };
        if (tab === "stt") setExtras((x) => ({ ...x, stt: [...x.stt, row] }));
        else setExtras((x) => ({ ...x, tts: [...x.tts, row] }));
      } else {
        const ak = vkApiKey.trim();
        const sk = vkSecretKey.trim();
        if (!ak || !sk) {
          setStatusMsg("Для T-Bank VoiceKit укажите API key и secret key.");
          setStatusError(true);
          return;
        }
        const kind = tab === "stt" ? PANEL_EXTRA_KIND.TBANK_VK_STT : PANEL_EXTRA_KIND.TBANK_VK_TTS;
        const row = {
          id: newExtraId(),
          name,
          kind,
          value: "",
          config: {
            api_key: ak,
            secret_key: sk,
            endpoint: vkEndpoint.trim(),
          },
        };
        if (tab === "stt") setExtras((x) => ({ ...x, stt: [...x.stt, row] }));
        else setExtras((x) => ({ ...x, tts: [...x.tts, row] }));
      }
    }
    setAddModalOpen(false);
    setStatusMsg("Запись добавлена. Не забудьте нажать «Сохранить».");
    setStatusError(false);
  };

  const removeExtra = (tab, id) => {
    if (tab === "llm") setExtras((x) => ({ ...x, llm: x.llm.filter((r) => r.id !== id) }));
    else if (tab === "stt") setExtras((x) => ({ ...x, stt: x.stt.filter((r) => r.id !== id) }));
    else setExtras((x) => ({ ...x, tts: x.tts.filter((r) => r.id !== id) }));
  };

  const llmRangeValue = Math.round(form.llmTemp * 10);
  const inputClass =
    "w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500";
  const labelClass = "text-sm font-medium text-slate-200";
  const helpClass = "text-xs text-slate-500";
  const tableShell = "overflow-x-auto rounded-2xl border border-slate-800 bg-slate-900/70";
  const th = "px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500";
  const td = "px-4 py-3 align-top text-sm text-slate-200";

  const modalRoot = typeof document !== "undefined" ? document.body : null;
  const activeExtras =
    settingsTab === "llm" ? extras.llm : settingsTab === "stt" ? extras.stt : extras.tts;

  return (
    <div className={`w-full min-w-0 ${PAGE_TEXT}`}>
      <header className={PAGE_HEADER_BETWEEN}>
        <div className="flex items-center gap-3">
          <Settings className={PAGE_TITLE_ICON} strokeWidth={1.5} aria-hidden />
          <h1 className={PAGE_H1}>Настройки системы</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={loadSettings}
            disabled={loading}
            className={BTN_RELOAD_ICON}
            aria-label="Обновить"
            title="Обновить"
          >
            <RefreshCcw
              className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
              strokeWidth={2}
              aria-hidden
            />
          </button>
          <button
            type="button"
            className={BTN_ADD}
            onClick={openAddModal}
            title="Добавить запись"
          >
            <Plus className={ICON_BTN} strokeWidth={2} aria-hidden />
            Добавить
          </button>
        </div>
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
        <form className="space-y-4" onSubmit={onSubmit}>
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
            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-slate-100">LLM (DeepSeek / OpenAI)</h2>
              <p className="text-sm text-slate-400">Основные параметры модели и API-ключи.</p>
              <div className={tableShell}>
                <table className="min-w-full divide-y divide-slate-800 text-left">
                  <thead className="bg-slate-900/60">
                    <tr>
                      <th className={th}>Параметр</th>
                      <th className={th}>Значение</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    <tr className="hover:bg-slate-800/20">
                      <td className={`${td} w-[min(12rem,30vw)] font-medium`}>Провайдер LLM</td>
                      <td className={td}>
                        <select
                          id="llm-provider"
                          className={inputClass}
                          value={form.llmProvider}
                          onChange={(e) => {
                            const v = e.target.value;
                            setForm((f) => ({
                              ...f,
                              llmProvider: v,
                              llmModel: v === "openai" ? "gpt-4o-mini" : "deepseek-chat",
                            }));
                          }}
                        >
                          <option value="deepseek">DeepSeek</option>
                          <option value="openai">OpenAI</option>
                        </select>
                      </td>
                    </tr>
                    <tr className="hover:bg-slate-800/20">
                      <td className={`${td} w-[min(12rem,30vw)] font-medium`}>Модель</td>
                      <td className={td}>
                        <p className={helpClass}>
                          Идентификатор chat-модели для выбранного провайдера. Список обновляется с API, если
                          задан ключ.{" "}
                          {llmModelsSource === "api" ? (
                            <span className="text-emerald-400/90">(загружено с API)</span>
                          ) : llmModelsSource === "fallback" ? (
                            <span className="text-amber-400/90">(статический список: нет ключа или ошибка)</span>
                          ) : null}
                        </p>
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                          <input
                            id="llm-model"
                            className={`${inputClass} min-w-[12rem] flex-1 font-mono text-sm`}
                            list="llm-model-suggestions"
                            type="text"
                            autoComplete="off"
                            placeholder={form.llmProvider === "openai" ? "gpt-4o-mini" : "deepseek-chat"}
                            value={form.llmModel}
                            onChange={(e) => setField("llmModel", e.target.value)}
                            maxLength={128}
                            aria-label="Модель LLM"
                          />
                          <datalist id="llm-model-suggestions">
                            {llmModelOptions.map((m) => (
                              <option key={m} value={m} />
                            ))}
                          </datalist>
                          <button
                            type="button"
                            className={BTN_RELOAD_ICON}
                            title="Обновить список моделей"
                            onClick={() => loadLlmModelList()}
                            disabled={llmModelsLoading}
                            aria-label="Обновить список моделей"
                          >
                            <RefreshCcw
                              className={`h-4 w-4 ${llmModelsLoading ? "animate-spin" : ""}`}
                              aria-hidden
                            />
                          </button>
                        </div>
                      </td>
                    </tr>
                    <tr className="hover:bg-slate-800/20">
                      <td className={`${td} font-medium`}>
                        <span aria-hidden>🌡</span> Температура LLM
                      </td>
                      <td className={td}>
                        <div className="flex flex-wrap items-center gap-3">
                          <input
                            type="range"
                            min={0}
                            max={10}
                            step={1}
                            value={llmRangeValue}
                            onChange={onLlmRangeInput}
                            className="min-w-[10rem] flex-1 accent-sky-500"
                            aria-label="Температура LLM"
                          />
                          <input
                            className={`${inputClass} w-20 shrink-0`}
                            type="number"
                            min={0}
                            max={1}
                            step={0.1}
                            value={form.llmTemp}
                            onInput={onLlmNumberInput}
                            onChange={onLlmNumberInput}
                          />
                        </div>
                      </td>
                    </tr>
                    <tr className="hover:bg-slate-800/20">
                      <td className={`${td} font-medium`}>
                        <span className="inline-flex items-center">
                          <DeepSeekGlyph />
                          Ключ DeepSeek API
                        </span>
                      </td>
                      <td className={td}>
                        <p className={helpClass}>{form.hints.deepseek}</p>
                        <input
                          className={inputClass}
                          type="password"
                          autoComplete="off"
                          placeholder="Пусто — не менять ключ"
                          value={form.deepseekKey}
                          onChange={(e) => setField("deepseekKey", e.target.value)}
                        />
                      </td>
                    </tr>
                    <tr className="hover:bg-slate-800/20">
                      <td className={`${td} font-medium`}>Ключ OpenAI API</td>
                      <td className={td}>
                        <p className={helpClass}>{form.hints.openai}</p>
                        <input
                          className={inputClass}
                          type="password"
                          autoComplete="off"
                          placeholder="Пусто — не менять ключ"
                          value={form.openaiKey}
                          onChange={(e) => setField("openaiKey", e.target.value)}
                        />
                      </td>
                    </tr>
                    <tr className="hover:bg-slate-800/20">
                      <td className={`${td} font-medium`}>Лимит сообщений в контексте</td>
                      <td className={td}>
                        <p className={helpClass}>Сколько последних реплик (user/assistant) подмешивать в запрос</p>
                        <input
                          className={`${inputClass} max-w-[12rem]`}
                          type="number"
                          min={1}
                          max={200}
                          step={1}
                          value={form.maxContextLimit}
                          onChange={(e) => setField("maxContextLimit", e.target.value)}
                        />
                      </td>
                    </tr>
                    <tr className="hover:bg-slate-800/20">
                      <td className={`${td} font-medium`}>Веб-поиск</td>
                      <td className={td}>
                        <label className="inline-flex cursor-pointer items-center gap-2 text-slate-200">
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-slate-500 bg-slate-900 accent-sky-500"
                            checked={form.enableWebSearch}
                            onChange={(e) => setField("enableWebSearch", e.target.checked)}
                          />
                          Разрешить веб-поиск
                        </label>
                      </td>
                    </tr>
                    {activeExtras.map((r) => (
                      <tr key={r.id} className="hover:bg-slate-800/20">
                        <td className={`${td} font-medium`}>{r.name}</td>
                        <td className={td}>
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            <span className="whitespace-pre-wrap break-words text-slate-300">{r.value}</span>
                            <IconDeleteButton
                              title="Удалить запись"
                              onClick={() => removeExtra("llm", r.id)}
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          {settingsTab === "stt" ? (
            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-slate-100">STT</h2>
              <p className="text-sm text-slate-400">
                SaluteSpeech (основной блок выше) и отдельные подключения, в т.ч.{" "}
                <a
                  className="text-emerald-400 underline decoration-emerald-600/50 underline-offset-2 hover:text-emerald-300"
                  href="https://developer.tbank.ru/voicekit/intro"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  T-Bank VoiceKit
                </a>{" "}
                (gRPC/REST, см.{" "}
                <a
                  className="text-emerald-400 underline decoration-emerald-600/50 underline-offset-2 hover:text-emerald-300"
                  href="https://developer.tbank.ru/voicekit/api/speech-recognition"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  распознавание речи
                </a>
                ; интеграция с Asterisk:{" "}
                <a
                  className="text-emerald-400 underline decoration-emerald-600/50 underline-offset-2 hover:text-emerald-300"
                  href="https://github.com/Tinkoff/asterisk-voicekit-modules"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Tinkoff/asterisk-voicekit-modules
                </a>
                ).
              </p>
              <div className={tableShell}>
                <table className="min-w-full divide-y divide-slate-800 text-left">
                  <thead className="bg-slate-900/60">
                    <tr>
                      <th className={th}>Параметр</th>
                      <th className={th}>Значение</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    <tr className="hover:bg-slate-800/20">
                      <td className={`${td} w-[min(10rem,28vw)] font-medium`}>Ключ SaluteSpeech</td>
                      <td className={td}>
                        <p className={helpClass}>{form.hints.salutespeech}</p>
                        <input
                          className={inputClass}
                          type="password"
                          autoComplete="off"
                          placeholder="Пусто — не менять ключ"
                          value={form.salutespeechKey}
                          onChange={(e) => setField("salutespeechKey", e.target.value)}
                        />
                      </td>
                    </tr>
                    <tr className="hover:bg-slate-800/20">
                      <td className={`${td} font-medium`}>OAuth scope</td>
                      <td className={td}>
                        <input
                          className={inputClass}
                          type="text"
                          autoComplete="off"
                          placeholder="SALUTE_SPEECH_PERS"
                          value={form.salutespeechScope}
                          onChange={(e) => setField("salutespeechScope", e.target.value)}
                        />
                      </td>
                    </tr>
                    {activeExtras.map((r) => (
                      <tr key={r.id} className="hover:bg-slate-800/20">
                        <td className={`${td} font-medium`}>
                          {r.name}
                          {r.kind === PANEL_EXTRA_KIND.TBANK_VK_STT ? (
                            <span className="ml-2 inline-block rounded bg-amber-900/50 px-1.5 text-[10px] font-normal uppercase text-amber-200">
                              T-Bank STT
                            </span>
                          ) : null}
                        </td>
                        <td className={td}>
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            {r.kind === PANEL_EXTRA_KIND.TBANK_VK_STT && r.config ? (
                              <div className="min-w-0 text-xs text-slate-400">
                                <p>
                                  <span className="text-slate-500">API key:</span>{" "}
                                  <span className="font-mono text-slate-300">
                                    {r.config.api_key || "—"}
                                  </span>
                                </p>
                                <p>
                                  <span className="text-slate-500">Secret:</span>{" "}
                                  <span className="font-mono text-slate-300">
                                    {r.config.secret_key || "—"}
                                  </span>
                                </p>
                                {r.config.endpoint ? (
                                  <p>
                                    <span className="text-slate-500">Endpoint:</span> {r.config.endpoint}
                                  </p>
                                ) : null}
                              </div>
                            ) : (
                              <span className="whitespace-pre-wrap break-words text-slate-300">
                                {r.value}
                              </span>
                            )}
                            <IconDeleteButton
                              title="Удалить запись"
                              onClick={() => removeExtra("stt", r.id)}
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          {settingsTab === "tts" ? (
            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-slate-100">TTS</h2>
              <p className="text-sm text-slate-400">
                SaluteSpeech (поле «Голос TTS») и варианты на базе{" "}
                <a
                  className="text-emerald-400 underline decoration-emerald-600/50 underline-offset-2 hover:text-emerald-300"
                  href="https://developer.tbank.ru/voicekit/intro"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  T-Bank VoiceKit
                </a>{" "}
                (синтез для юрлиц, см. портал T-API; Asterisk:{" "}
                <a
                  className="text-emerald-400 underline decoration-emerald-600/50 underline-offset-2 hover:text-emerald-300"
                  href="https://github.com/Tinkoff/asterisk-voicekit-modules"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  модули VoiceKit
                </a>
                ).
              </p>
              <div className={tableShell}>
                <table className="min-w-full divide-y divide-slate-800 text-left">
                  <thead className="bg-slate-900/60">
                    <tr>
                      <th className={th}>Параметр</th>
                      <th className={th}>Значение</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    <tr className="hover:bg-slate-800/20">
                      <td className={`${td} w-[min(10rem,28vw)] font-medium`}>Голос TTS</td>
                      <td className={td}>
                        <input
                          className={inputClass}
                          type="text"
                          autoComplete="off"
                          placeholder="Ost_24000"
                          value={form.salutespeechVoice}
                          onChange={(e) => setField("salutespeechVoice", e.target.value)}
                        />
                      </td>
                    </tr>
                    {activeExtras.map((r) => (
                      <tr key={r.id} className="hover:bg-slate-800/20">
                        <td className={`${td} font-medium`}>
                          {r.name}
                          {r.kind === PANEL_EXTRA_KIND.TBANK_VK_TTS ? (
                            <span className="ml-2 inline-block rounded bg-amber-900/50 px-1.5 text-[10px] font-normal uppercase text-amber-200">
                              T-Bank TTS
                            </span>
                          ) : null}
                        </td>
                        <td className={td}>
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            {r.kind === PANEL_EXTRA_KIND.TBANK_VK_TTS && r.config ? (
                              <div className="min-w-0 text-xs text-slate-400">
                                <p>
                                  <span className="text-slate-500">API key:</span>{" "}
                                  <span className="font-mono text-slate-300">
                                    {r.config.api_key || "—"}
                                  </span>
                                </p>
                                <p>
                                  <span className="text-slate-500">Secret:</span>{" "}
                                  <span className="font-mono text-slate-300">
                                    {r.config.secret_key || "—"}
                                  </span>
                                </p>
                                {r.config.endpoint ? (
                                  <p>
                                    <span className="text-slate-500">Endpoint:</span> {r.config.endpoint}
                                  </p>
                                ) : null}
                              </div>
                            ) : (
                              <span className="whitespace-pre-wrap break-words text-slate-300">
                                {r.value}
                              </span>
                            )}
                            <IconDeleteButton
                              title="Удалить запись"
                              onClick={() => removeExtra("tts", r.id)}
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          <div className="pt-2">
            <button type="submit" className={BTN_SAVE} disabled={saving}>
              <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
              Сохранить
            </button>
          </div>
        </form>
      )}

      {addModalOpen && modalRoot
        ? createPortal(
            <div
              className="fixed inset-0 z-[100] flex items-center justify-center overflow-y-auto bg-black/60 p-4"
              role="dialog"
              aria-modal="true"
              aria-labelledby="settings-add-title"
            >
              <div
                className={`w-full rounded-xl border border-slate-800 bg-slate-900 p-5 shadow-xl ${
                  settingsTab === "llm" ? "max-w-md" : "max-w-lg"
                }`}
              >
                <h2 id="settings-add-title" className="mb-1 text-lg font-semibold text-white">
                  Новая запись:{" "}
                  {settingsTab === "llm" ? "LLM" : settingsTab === "stt" ? "STT" : "TTS"}
                </h2>
                {settingsTab === "llm" ? (
                  <p className="mb-4 text-sm text-slate-400">
                    Произвольная подпись и текст (сохраняется в таблицу).
                  </p>
                ) : (
                  <p className="mb-3 text-sm text-slate-400">
                    Текстовая заметка или подключение{" "}
                    <a
                      className="text-emerald-400 underline"
                      href="https://developer.tbank.ru/voicekit/intro"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      T-Bank VoiceKit
                    </a>{" "}
                    (в личном кабинете T-API: пары <strong className="text-slate-200">API key / Secret key</strong>).
                  </p>
                )}

                {settingsTab === "llm" ? (
                  <div className="space-y-3">
                    <div>
                      <label className={`${labelClass} mb-1 block`} htmlFor="add-ex-name">
                        Название
                      </label>
                      <input
                        id="add-ex-name"
                        className={inputClass}
                        value={addName}
                        onChange={(e) => setAddName(e.target.value)}
                        placeholder="Например: Примечание"
                      />
                    </div>
                    <div>
                      <label className={`${labelClass} mb-1 block`} htmlFor="add-ex-val">
                        Значение
                      </label>
                      <textarea
                        id="add-ex-val"
                        className={`${inputClass} min-h-[6rem] resize-y`}
                        value={addValue}
                        onChange={(e) => setAddValue(e.target.value)}
                        placeholder="Текст"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                      <span className={`${labelClass} shrink-0`}>Тип</span>
                      <div className="flex flex-wrap gap-3">
                        <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-slate-200">
                          <input
                            type="radio"
                            className="accent-sky-500"
                            name="stt-tts-mode"
                            checked={sttTtsAddMode === "voicekit"}
                            onChange={() => setSttTtsAddMode("voicekit")}
                          />
                          T-Bank VoiceKit
                        </label>
                        <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-slate-200">
                          <input
                            type="radio"
                            className="accent-sky-500"
                            name="stt-tts-mode"
                            checked={sttTtsAddMode === "note"}
                            onChange={() => setSttTtsAddMode("note")}
                          />
                          Текстовая заметка
                        </label>
                      </div>
                    </div>
                    <div>
                      <label className={`${labelClass} mb-1 block`} htmlFor="add-ex-name">
                        Название
                      </label>
                      <input
                        id="add-ex-name"
                        className={inputClass}
                        value={addName}
                        onChange={(e) => setAddName(e.target.value)}
                        placeholder={
                          sttTtsAddMode === "voicekit" ? "Например: Проект VoiceKit" : "Краткий заголовок"
                        }
                      />
                    </div>
                    {sttTtsAddMode === "note" ? (
                      <div>
                        <label className={`${labelClass} mb-1 block`} htmlFor="add-ex-val">
                          Значение
                        </label>
                        <textarea
                          id="add-ex-val"
                          className={`${inputClass} min-h-[6rem] resize-y`}
                          value={addValue}
                          onChange={(e) => setAddValue(e.target.value)}
                          placeholder="Текст"
                        />
                      </div>
                    ) : (
                      <>
                        <div>
                          <label className={`${labelClass} mb-1 block`} htmlFor="vk-api">
                            API key
                          </label>
                          <input
                            id="vk-api"
                            className={inputClass}
                            type="password"
                            autoComplete="off"
                            value={vkApiKey}
                            onChange={(e) => setVkApiKey(e.target.value)}
                            placeholder="Публичный ключ из кабинета T-API"
                          />
                        </div>
                        <div>
                          <label className={`${labelClass} mb-1 block`} htmlFor="vk-sec">
                            Secret key
                          </label>
                          <input
                            id="vk-sec"
                            className={inputClass}
                            type="password"
                            autoComplete="off"
                            value={vkSecretKey}
                            onChange={(e) => setVkSecretKey(e.target.value)}
                            placeholder="Секретный ключ (показывается один раз при выпуске)"
                          />
                        </div>
                        <div>
                          <label className={`${labelClass} mb-1 block`} htmlFor="vk-endp">
                            Endpoint (gRPC/REST, опционально)
                          </label>
                          <input
                            id="vk-endp"
                            className={inputClass}
                            type="text"
                            autoComplete="off"
                            value={vkEndpoint}
                            onChange={(e) => setVkEndpoint(e.target.value)}
                            placeholder="По документации VoiceKit, если требуется явный хост"
                          />
                          <p className="mt-1 text-xs text-slate-500">
                            Обычно хосты задаёт клиент по региону; оставьте пусто, если не требуется.
                          </p>
                        </div>
                        <p className="text-xs text-slate-500">
                          Док:{" "}
                          <a
                            className="text-emerald-400 underline"
                            href="https://developer.tbank.ru/voicekit/intro"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            введение
                          </a>
                          {" · "}
                          <a
                            className="text-emerald-400 underline"
                            href="https://developer.tbank.ru/voicekit/api/speech-recognition"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            STT API
                          </a>
                          {" · "}
                          <a
                            className="text-emerald-400 underline"
                            href="https://github.com/Tinkoff/asterisk-voicekit-modules"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            Asterisk
                          </a>
                        </p>
                      </>
                    )}
                  </div>
                )}

                <div className="mt-5 flex flex-wrap justify-end gap-2">
                  <button
                    type="button"
                    className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
                    onClick={closeAddModal}
                  >
                    Отмена
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500"
                    onClick={confirmAddModal}
                  >
                    <Plus className="h-3.5 w-3.5" aria-hidden />
                    Добавить
                  </button>
                </div>
              </div>
            </div>,
            modalRoot,
          )
        : null}
    </div>
  );
}
