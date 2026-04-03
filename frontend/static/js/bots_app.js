/**
 * Панель «Боты»: список сессий, WebSocket мониторинг, просмотр истории.
 */
(function () {
  "use strict";

  var API_CHATS = "/api/chats";
  var WS_PATH = "/api/ws/monitoring";

  var sessionsOrder = [];
  var sessionMap = {};
  var selectedSessionId = null;
  var ws = null;
  var pingTimer = null;

  function byId(id) {
    return document.getElementById(id);
  }

  function escapeHtml(s) {
    if (s == null) return "";
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function formatDate(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleString("ru-RU");
  }

  function wsUrl() {
    var p = location.protocol === "https:" ? "wss:" : "ws:";
    return p + "//" + location.host + WS_PATH;
  }

  function setWsStatus(text, isError) {
    var el = byId("bots-ws-status");
    if (!el) return;
    el.textContent = text || "";
    el.style.color = isError ? "#b91c1c" : "#15803d";
  }

  function upsertSessionRow(sessionId, preview, atIso, userLabel) {
    if (!sessionMap[sessionId]) {
      sessionMap[sessionId] = {
        session_id: sessionId,
        user_label: userLabel,
        last_preview: preview,
        last_at: atIso,
      };
      sessionsOrder.unshift(sessionId);
    } else {
      var row = sessionMap[sessionId];
      row.last_preview = preview;
      row.last_at = atIso;
      if (userLabel) row.user_label = userLabel;
      var idx = sessionsOrder.indexOf(sessionId);
      if (idx > 0) {
        sessionsOrder.splice(idx, 1);
        sessionsOrder.unshift(sessionId);
      }
    }
    renderTable();
  }

  function renderTable() {
    var tbody = byId("bots-tbody");
    if (!tbody) return;
    while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
    if (sessionsOrder.length === 0) {
      var tr0 = document.createElement("tr");
      tr0.id = "bots-empty-row";
      tr0.innerHTML =
        '<td colspan="3" class="calls-table__empty">Нет сохранённых сообщений. Напишите боту в MAX или в тестере чата.</td>';
      tbody.appendChild(tr0);
      return;
    }
    sessionsOrder.forEach(function (sid) {
      var rec = sessionMap[sid];
      var tr = document.createElement("tr");
      tr.setAttribute("data-session-id", sid);
      tr.style.cursor = "pointer";
      var title = rec.user_label ? rec.user_label + " (" + sid + ")" : sid;
      tr.innerHTML =
        "<td><code>" +
        escapeHtml(title) +
        "</code></td>" +
        "<td class=\"calls-table__snippet\">" +
        escapeHtml(rec.last_preview || "—") +
        "</td>" +
        "<td>" +
        escapeHtml(formatDate(rec.last_at)) +
        "</td>";
      tr.addEventListener("click", function () {
        openHistory(sid);
      });
      tbody.appendChild(tr);
    });
  }

  function mergeListItems(items) {
    sessionsOrder = [];
    sessionMap = {};
    (items || []).forEach(function (it) {
      sessionMap[it.session_id] = {
        session_id: it.session_id,
        user_label: it.user_label,
        last_preview: it.last_preview,
        last_at: it.last_at,
      };
      sessionsOrder.push(it.session_id);
    });
    renderTable();
  }

  function loadSessions() {
    fetch(API_CHATS, { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        mergeListItems(data.items || []);
      })
      .catch(function (e) {
        var tbody = byId("bots-tbody");
        if (tbody) {
          tbody.innerHTML =
            '<tr><td colspan="3" class="calls-table__empty calls-table__error">' +
            escapeHtml(e.message || String(e)) +
            "</td></tr>";
        }
      });
  }

  function openHistory(sessionId) {
    selectedSessionId = sessionId;
    var modal = byId("bots-history-modal");
    var backdrop = byId("bots-history-backdrop");
    var titleEl = byId("bots-history-session");
    var body = byId("bots-history-body");
    if (!modal || !body) return;
    titleEl.textContent = "Сессия: " + sessionId;
    body.innerHTML = "<p class=\"calls-table__empty\">Загрузка…</p>";
    modal.hidden = false;
    backdrop.hidden = false;

    fetch(API_CHATS + "/" + encodeURIComponent(sessionId), { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        renderHistoryBody(data.messages || []);
      })
      .catch(function (e) {
        body.innerHTML =
          "<p class=\"calls-table__error\">" + escapeHtml(e.message || String(e)) + "</p>";
      });
  }

  function renderHistoryBody(messages) {
    var body = byId("bots-history-body");
    if (!body) return;
    if (!messages.length) {
      body.innerHTML = "<p class=\"calls-table__empty\">Нет сообщений.</p>";
      return;
    }
    var html = '<div class="bots-history-list">';
    messages.forEach(function (m) {
      var roleRu = m.role === "user" ? "Пользователь" : m.role === "assistant" ? "Ассистент" : m.role;
      html +=
        '<div class="bots-history-msg">' +
        '<div class="bots-history-msg__meta">' +
        escapeHtml(roleRu) +
        " · " +
        escapeHtml(formatDate(m.created_at)) +
        "</div>" +
        '<pre class="bots-history-msg__text">' +
        escapeHtml(m.content || "") +
        "</pre>" +
        "</div>";
    });
    html += "</div>";
    body.innerHTML = html;
  }

  function closeHistory() {
    selectedSessionId = null;
    var modal = byId("bots-history-modal");
    var backdrop = byId("bots-history-backdrop");
    if (modal) modal.hidden = true;
    if (backdrop) backdrop.hidden = true;
  }

  function onWsMessage(ev) {
    try {
      var data = JSON.parse(ev.data);
      if (data.type !== "new_message") return;
      var sid = data.session_id;
      var preview = (data.content || "").slice(0, 280);
      var now = new Date().toISOString();
      var uinfo = data.user_info || "";
      upsertSessionRow(sid, preview, now, uinfo || null);
      if (selectedSessionId === sid) {
        fetch(API_CHATS + "/" + encodeURIComponent(sid), { credentials: "same-origin" })
          .then(function (r) {
            return r.json();
          })
          .then(function (d) {
            renderHistoryBody(d.messages || []);
          })
          .catch(function () {});
      }
    } catch (e) {
      console.warn(e);
    }
  }

  function connectWs() {
    if (ws) {
      try {
        ws.close();
      } catch (e) {}
    }
    setWsStatus("Подключение к мониторингу…", false);
    ws = new WebSocket(wsUrl());
    ws.onopen = function () {
      setWsStatus("Мониторинг: соединение активно.", false);
      if (pingTimer) clearInterval(pingTimer);
      pingTimer = setInterval(function () {
        if (ws && ws.readyState === WebSocket.OPEN) {
          try {
            ws.send("ping");
          } catch (e) {}
        }
      }, 25000);
    };
    ws.onmessage = onWsMessage;
    ws.onerror = function () {
      setWsStatus("Ошибка WebSocket (проверьте прокси и HTTPS).", true);
    };
    ws.onclose = function () {
      setWsStatus("Соединение мониторинга закрыто. Переподключение через 5 с…", true);
      if (pingTimer) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
      setTimeout(connectWs, 5000);
    };
  }

  function initTabs() {
    var tabBtns = document.querySelectorAll(".bots-tabs__btn[data-tab]");
    var panels = {
      max: byId("bots-tab-max"),
      telegram: byId("bots-tab-telegram"),
      vk: byId("bots-tab-vk"),
    };
    tabBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var key = btn.getAttribute("data-tab");
        if (!key) return;
        closeHistory();
        tabBtns.forEach(function (b) {
          var on = b === btn;
          b.classList.toggle("bots-tabs__btn--active", on);
          b.setAttribute("aria-selected", on ? "true" : "false");
        });
        Object.keys(panels).forEach(function (k) {
          var p = panels[k];
          if (p) p.hidden = k !== key;
        });
      });
    });
  }

  function init() {
    initTabs();
    loadSessions();
    connectWs();
    var closeBtn = byId("bots-history-close");
    if (closeBtn) closeBtn.addEventListener("click", closeHistory);
    var backdrop = byId("bots-history-backdrop");
    if (backdrop) backdrop.addEventListener("click", closeHistory);
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") closeHistory();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
