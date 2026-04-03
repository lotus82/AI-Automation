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
    MAX_BOT_TOKEN: "MAX_BOT_TOKEN",
    MAX_USE_POLLING: "MAX_USE_POLLING",
    MAX_CONTEXT_LIMIT: "MAX_CONTEXT_LIMIT",
    MAX_BOT_USERNAME: "MAX_BOT_USERNAME",
    MAX_GROUP_CHAT_ID: "MAX_GROUP_CHAT_ID",
    MAX_GROUP_ADDITIONAL_PROMPT: "MAX_GROUP_ADDITIONAL_PROMPT",
    SALUTESPEECH_AUTH_KEY: "SALUTESPEECH_AUTH_KEY",
    SALUTESPEECH_SCOPE: "SALUTESPEECH_SCOPE",
    SALUTESPEECH_VOICE: "SALUTESPEECH_VOICE",
    DEFAULT_CONSULTANT_PROMPT: "DEFAULT_CONSULTANT_PROMPT",
    TEXT_BOT_SYSTEM_SUPPLEMENT: "TEXT_BOT_SYSTEM_SUPPLEMENT",
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
    hintFor(KEYS.MAX_BOT_TOKEN, "max-bot-mask-hint");
    hintFor(KEYS.SALUTESPEECH_AUTH_KEY, "salutespeech-mask-hint");

    byId("deepseek-key").value = "";
    byId("openai-key").value = "";
    byId("telegram-token").value = "";
    byId("max-bot-token").value = "";
    byId("salutespeech-key").value = "";

    var ssScope = map[KEYS.SALUTESPEECH_SCOPE];
    if (ssScope) byId("salutespeech-scope").value = ssScope.value || "";
    var ssVoice = map[KEYS.SALUTESPEECH_VOICE];
    if (ssVoice) byId("salutespeech-voice").value = ssVoice.value || "";

    var c = map[KEYS.DEFAULT_CONSULTANT_PROMPT];
    if (c) byId("consultant-prompt").value = c.value || "";

    var tbs = map[KEYS.TEXT_BOT_SYSTEM_SUPPLEMENT];
    var tbsEl = byId("text-bot-supplement");
    if (tbsEl) {
      tbsEl.value = tbs ? (tbs.value != null ? String(tbs.value) : "") : "";
    }

    var a = map[KEYS.ANALYST_QA_PROMPT];
    if (a) byId("analyst-prompt").value = a.value || "";

    var mxc = map[KEYS.MAX_CONTEXT_LIMIT];
    var mxcEl = byId("max-context-limit");
    if (mxcEl) {
      mxcEl.value =
        mxc && mxc.value && String(mxc.value).trim() !== ""
          ? String(mxc.value).trim()
          : "10";
    }

    var mPoll = map[KEYS.MAX_USE_POLLING];
    var pollEl = byId("max-use-polling");
    if (pollEl) {
      var pv = mPoll && mPoll.value ? String(mPoll.value).trim().toLowerCase() : "1";
      pollEl.checked = pv === "1" || pv === "true" || pv === "yes" || pv === "on";
    }

    var mbu = map[KEYS.MAX_BOT_USERNAME];
    var mbuEl = byId("max-bot-username");
    if (mbuEl) {
      mbuEl.value = mbu && mbu.value != null ? String(mbu.value) : "";
    }
    var mgc = map[KEYS.MAX_GROUP_CHAT_ID];
    var mgcEl = byId("max-group-chat-id");
    if (mgcEl) {
      mgcEl.value = mgc && mgc.value != null ? String(mgc.value) : "";
    }
    var mgp = map[KEYS.MAX_GROUP_ADDITIONAL_PROMPT];
    var mgpEl = byId("max-group-prompt");
    if (mgpEl) {
      mgpEl.value = mgp && mgp.value != null ? String(mgp.value) : "";
    }
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
    var tbsEl2 = byId("text-bot-supplement");
    if (tbsEl2) values[KEYS.TEXT_BOT_SYSTEM_SUPPLEMENT] = tbsEl2.value;
    values[KEYS.ANALYST_QA_PROMPT] = byId("analyst-prompt").value;
    values[KEYS.SALUTESPEECH_SCOPE] =
      byId("salutespeech-scope").value.trim() || "SALUTE_SPEECH_PERS";
    values[KEYS.SALUTESPEECH_VOICE] = byId("salutespeech-voice").value.trim() || "Ost_24000";

    var lim = parseInt(byId("max-context-limit").value, 10);
    if (isNaN(lim)) lim = 10;
    lim = Math.max(1, Math.min(200, lim));
    values[KEYS.MAX_CONTEXT_LIMIT] = String(lim);

    var pollChk = byId("max-use-polling");
    if (pollChk) {
      values[KEYS.MAX_USE_POLLING] = pollChk.checked ? "1" : "0";
    }

    var mbuEl2 = byId("max-bot-username");
    if (mbuEl2) values[KEYS.MAX_BOT_USERNAME] = mbuEl2.value.trim();
    var mgcEl2 = byId("max-group-chat-id");
    if (mgcEl2) values[KEYS.MAX_GROUP_CHAT_ID] = mgcEl2.value.trim();
    var mgpEl2 = byId("max-group-prompt");
    if (mgpEl2) values[KEYS.MAX_GROUP_ADDITIONAL_PROMPT] = mgpEl2.value;

    [
      KEYS.DEEPSEEK_API_KEY,
      KEYS.OPENAI_API_KEY,
      KEYS.TELEGRAM_BOT_TOKEN,
      KEYS.MAX_BOT_TOKEN,
      KEYS.SALUTESPEECH_AUTH_KEY,
    ].forEach(function (k) {
      var inputId =
        k === KEYS.DEEPSEEK_API_KEY
          ? "deepseek-key"
          : k === KEYS.OPENAI_API_KEY
            ? "openai-key"
            : k === KEYS.TELEGRAM_BOT_TOKEN
              ? "telegram-token"
              : k === KEYS.MAX_BOT_TOKEN
                ? "max-bot-token"
                : "salutespeech-key";
      var v = byId(inputId).value.trim();
      if (v) values[k] = v;
    });

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
