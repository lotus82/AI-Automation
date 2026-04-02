/**
 * Режим отладки панели «Боты»: симулятор вебхука MAX и поток логов с сервера.
 */
(function () {
  "use strict";

  var WEBHOOK_URL = "/api/max/webhook";
  var WS_LOGS_PATH = "/api/ws/logs";

  var logWs = null;
  var logPingTimer = null;

  function byId(id) {
    return document.getElementById(id);
  }

  function escapeHtml(s) {
    if (s == null) return "";
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function wsLogsUrl() {
    var p = location.protocol === "https:" ? "wss:" : "ws:";
    return p + "//" + location.host + WS_LOGS_PATH;
  }

  function levelClass(level) {
    var u = (level || "").toUpperCase();
    if (u === "ERROR" || u === "CRITICAL") return "log-line--error";
    if (u === "WARNING" || u === "WARN") return "log-line--warning";
    if (u === "DEBUG") return "log-line--debug";
    return "log-line--info";
  }

  function appendLogLine(level, text) {
    var win = byId("bots-debug-log-window");
    if (!win) return;
    var line = document.createElement("div");
    line.className = levelClass(level);
    line.textContent = text;
    win.appendChild(line);
    win.scrollTop = win.scrollHeight;
  }

  function connectLogWs() {
    if (logWs) {
      try {
        logWs.close();
      } catch (e) {}
      logWs = null;
    }
    var meta = byId("bots-debug-log-meta");
    if (meta) meta.textContent = "Подключение к потоку логов…";

    logWs = new WebSocket(wsLogsUrl());
    logWs.onopen = function () {
      if (meta) meta.textContent = "Логи: WebSocket активен.";
      if (logPingTimer) clearInterval(logPingTimer);
      logPingTimer = setInterval(function () {
        if (logWs && logWs.readyState === WebSocket.OPEN) {
          try {
            logWs.send("ping");
          } catch (e) {}
        }
      }, 25000);
    };
    logWs.onmessage = function (ev) {
      try {
        var data = JSON.parse(ev.data);
        if (data.type !== "log") return;
        var msg = data.message || "";
        appendLogLine(data.level, msg);
      } catch (e) {
        appendLogLine("INFO", String(ev.data || ""));
      }
    };
    logWs.onerror = function () {
      if (meta) {
        meta.textContent = "Ошибка WebSocket логов (проверьте прокси Nginx).";
        meta.style.color = "#f87171";
      }
    };
    logWs.onclose = function () {
      if (logPingTimer) {
        clearInterval(logPingTimer);
        logPingTimer = null;
      }
      var dbg = byId("bots-debug-mode");
      if (dbg && dbg.checked && meta) {
        meta.textContent = "Соединение логов закрыто. Переподключение через 4 с…";
        meta.style.color = "";
        setTimeout(function () {
          if (byId("bots-debug-mode") && byId("bots-debug-mode").checked) {
            connectLogWs();
          }
        }, 4000);
      }
    };
  }

  function disconnectLogWs() {
    if (logPingTimer) {
      clearInterval(logPingTimer);
      logPingTimer = null;
    }
    if (logWs) {
      try {
        logWs.close();
      } catch (e) {}
      logWs = null;
    }
    var meta = byId("bots-debug-log-meta");
    if (meta) {
      meta.textContent = "Поток логов отключён (включите «Режим отладки»).";
      meta.style.color = "";
    }
  }

  function toggleDebugView() {
    var chk = byId("bots-debug-mode");
    var main = byId("bots-main-view");
    var dbg = byId("bots-debug-view");
    if (!chk || !main || !dbg) return;
    if (chk.checked) {
      main.hidden = true;
      dbg.hidden = false;
      connectLogWs();
    } else {
      dbg.hidden = true;
      main.hidden = false;
      disconnectLogWs();
    }
  }

  function sendWebhook(ev) {
    if (ev && ev.preventDefault) ev.preventDefault();
    var ta = byId("bots-debug-webhook-json");
    var statusEl = byId("bots-debug-webhook-status");
    if (!ta || !statusEl) return;
    var raw = ta.value.trim();
    if (!raw) {
      statusEl.textContent = "Введите JSON тела запроса.";
      statusEl.className = "bots-debug-status bots-debug-status--err";
      return;
    }
    var body;
    try {
      body = JSON.parse(raw);
    } catch (e) {
      statusEl.textContent = "Некорректный JSON: " + (e.message || String(e));
      statusEl.className = "bots-debug-status bots-debug-status--err";
      return;
    }
    statusEl.textContent = "Отправка…";
    statusEl.className = "bots-debug-status";

    fetch(WEBHOOK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(body),
    })
      .then(function (r) {
        return r
          .json()
          .then(function (j) {
            return { ok: r.ok, status: r.status, json: j };
          })
          .catch(function () {
            return { ok: r.ok, status: r.status, json: null };
          });
      })
      .then(function (res) {
        var tail = res.json ? " — " + JSON.stringify(res.json) : "";
        statusEl.textContent = "HTTP " + res.status + tail;
        statusEl.className =
          res.ok && res.status < 400
            ? "bots-debug-status bots-debug-status--ok"
            : "bots-debug-status bots-debug-status--err";
      })
      .catch(function (e) {
        statusEl.textContent = "Сбой запроса: " + (e.message || String(e));
        statusEl.className = "bots-debug-status bots-debug-status--err";
      });
  }

  function init() {
    var chk = byId("bots-debug-mode");
    var form = byId("bots-debug-webhook-form");
    if (chk) {
      chk.addEventListener("change", toggleDebugView);
    }
    if (form) {
      form.addEventListener("submit", sendWebhook);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
