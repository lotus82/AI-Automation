/**
 * Загрузка и сохранение динамических настроек через /api/settings.
 */
(function () {
  "use strict";

  var KEYS = {
    LLM_PROVIDER: "LLM_PROVIDER",
    DEEPSEEK_API_KEY: "DEEPSEEK_API_KEY",
    OPENAI_API_KEY: "OPENAI_API_KEY",
    TELEGRAM_BOT_TOKEN: "TELEGRAM_BOT_TOKEN",
    SALUTESPEECH_AUTH_KEY: "SALUTESPEECH_AUTH_KEY",
    SALUTESPEECH_SCOPE: "SALUTESPEECH_SCOPE",
    SALUTESPEECH_VOICE: "SALUTESPEECH_VOICE",
    DEFAULT_CONSULTANT_PROMPT: "DEFAULT_CONSULTANT_PROMPT",
    ANALYST_QA_PROMPT: "ANALYST_QA_PROMPT",
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function setStatus(msg, isError) {
    var el = byId("settings-status");
    if (!el) return;
    el.textContent = msg || "";
    el.style.color = isError ? "#b91c1c" : "#15803d";
  }

  function mapFromList(rows) {
    var m = {};
    (rows || []).forEach(function (r) {
      m[r.key] = r;
    });
    return m;
  }

  function loadForm(map) {
    var p = map[KEYS.LLM_PROVIDER];
    if (p) {
      byId("llm-provider").value = (p.value || "deepseek").toLowerCase();
    }

    function hintFor(secretKey, hintId) {
      var row = map[secretKey];
      var hint = byId(hintId);
      if (!hint || !row) return;
      if (row.value && String(row.value).indexOf("…") !== -1) {
        hint.textContent = "Текущее значение (маска): " + row.value;
      } else if (row.value) {
        hint.textContent = "Ключ задан.";
      } else {
        hint.textContent = "Ключ не задан.";
      }
    }

    hintFor(KEYS.DEEPSEEK_API_KEY, "deepseek-mask-hint");
    hintFor(KEYS.OPENAI_API_KEY, "openai-mask-hint");
    hintFor(KEYS.TELEGRAM_BOT_TOKEN, "telegram-mask-hint");
    hintFor(KEYS.SALUTESPEECH_AUTH_KEY, "salutespeech-mask-hint");

    byId("deepseek-key").value = "";
    byId("openai-key").value = "";
    byId("telegram-token").value = "";
    byId("salutespeech-key").value = "";

    var ssScope = map[KEYS.SALUTESPEECH_SCOPE];
    if (ssScope) byId("salutespeech-scope").value = ssScope.value || "";
    var ssVoice = map[KEYS.SALUTESPEECH_VOICE];
    if (ssVoice) byId("salutespeech-voice").value = ssVoice.value || "";

    var c = map[KEYS.DEFAULT_CONSULTANT_PROMPT];
    if (c) byId("consultant-prompt").value = c.value || "";

    var a = map[KEYS.ANALYST_QA_PROMPT];
    if (a) byId("analyst-prompt").value = a.value || "";
  }

  async function loadSettings() {
    setStatus("Загрузка…", false);
    try {
      var res = await fetch("/api/settings");
      if (!res.ok) throw new Error("HTTP " + res.status);
      var rows = await res.json();
      loadForm(mapFromList(rows));
      setStatus("Настройки загружены.", false);
    } catch (e) {
      console.error(e);
      setStatus("Не удалось загрузить настройки: " + (e.message || e), true);
    }
  }

  function collectPayload() {
    var values = {};
    values[KEYS.LLM_PROVIDER] = byId("llm-provider").value.trim();
    values[KEYS.DEFAULT_CONSULTANT_PROMPT] = byId("consultant-prompt").value;
    values[KEYS.ANALYST_QA_PROMPT] = byId("analyst-prompt").value;
    values[KEYS.SALUTESPEECH_SCOPE] =
      byId("salutespeech-scope").value.trim() || "SALUTE_SPEECH_PERS";
    values[KEYS.SALUTESPEECH_VOICE] = byId("salutespeech-voice").value.trim() || "Ost_24000";

    [KEYS.DEEPSEEK_API_KEY, KEYS.OPENAI_API_KEY, KEYS.TELEGRAM_BOT_TOKEN, KEYS.SALUTESPEECH_AUTH_KEY].forEach(
      function (k) {
        var inputId =
          k === KEYS.DEEPSEEK_API_KEY
            ? "deepseek-key"
            : k === KEYS.OPENAI_API_KEY
              ? "openai-key"
              : k === KEYS.TELEGRAM_BOT_TOKEN
                ? "telegram-token"
                : "salutespeech-key";
        var v = byId(inputId).value.trim();
        if (v) values[k] = v;
      }
    );

    return values;
  }

  async function saveSettings(ev) {
    ev.preventDefault();
    setStatus("Сохранение…", false);
    try {
      var res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values: collectPayload() }),
      });
      if (!res.ok) {
        var errBody = await res.text();
        throw new Error(res.status + " " + errBody);
      }
      setStatus("Сохранено.", false);
      await loadSettings();
    } catch (e) {
      console.error(e);
      setStatus("Ошибка сохранения: " + (e.message || e), true);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = byId("settings-form");
    if (form) form.addEventListener("submit", saveSettings);
    loadSettings();
  });
})();
