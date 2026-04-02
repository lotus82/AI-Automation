/**
 * Дашборд: загрузка списка звонков и ОКК через REST (fetch /api/calls).
 * TODO: Добавить кнопку «Обновить» и обработку пагинации при росте таблицы.
 */
(function () {
  "use strict";

  var API_CALLS = "/api/calls";

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
    var pad = function (n) {
      return n < 10 ? "0" + n : String(n);
    };
    return (
      d.getFullYear() +
      "-" +
      pad(d.getMonth() + 1) +
      "-" +
      pad(d.getDate()) +
      " " +
      pad(d.getHours()) +
      ":" +
      pad(d.getMinutes())
    );
  }

  function snippet(text, maxLen) {
    if (!text) return "—";
    if (text.length <= maxLen) return text;
    return text.slice(0, maxLen) + "…";
  }

  function setNavActive() {
    var path = window.location.pathname.replace(/\/$/, "") || "/";
    var links = document.querySelectorAll(".nav__link[data-nav]");
    links.forEach(function (a) {
      var key = a.getAttribute("data-nav");
      var active = false;
      if (key === "home" && (path === "/" || path.endsWith("/index.html"))) active = true;
      if (key === "tester" && path.indexOf("tester") !== -1) active = true;
      if (key === "scenarios" && path.indexOf("scenarios") !== -1) active = true;
      if (key === "telephony" && path.indexOf("telephony") !== -1) active = true;
      if (key === "settings" && path.indexOf("settings") !== -1) active = true;
      if (key === "knowledge" && path.indexOf("knowledge") !== -1) active = true;
      a.classList.toggle("nav__link--active", active);
    });
  }

  function renderCallsTable(items) {
    var tbody = document.getElementById("calls-tbody");
    var emptyRow = document.getElementById("calls-empty-row");
    if (!tbody) return;

    while (tbody.firstChild) {
      tbody.removeChild(tbody.firstChild);
    }

    if (!items || items.length === 0) {
      var tr0 = document.createElement("tr");
      tr0.id = "calls-empty-row";
      tr0.innerHTML =
        '<td colspan="10" class="calls-table__empty">Пока нет записей. Завершите голосовой звонок или вызовите <code>POST /api/chat/finalize</code>.</td>';
      tbody.appendChild(tr0);
      return;
    }

    items.forEach(function (row) {
      var rec = row;
      var an = rec.analytics;
      var tr = document.createElement("tr");
      var recUrl = API_CALLS + "/" + encodeURIComponent(rec.id) + "/recording";
      var audioCell = "—";
      if (rec.has_audio) {
        audioCell =
          '<audio controls preload="none" src="' +
          escapeHtml(recUrl) +
          '" class="calls-table__audio-el"></audio> ' +
          '<a class="calls-table__link" href="' +
          escapeHtml(recUrl) +
          '" download>скачать</a> ' +
          '<button type="button" class="calls-table__btn-del" data-call-id="' +
          escapeHtml(rec.id) +
          '">удалить</button>';
      }
      tr.innerHTML =
        "<td><code>" +
        escapeHtml(rec.session_id) +
        "</code></td>" +
        "<td>" +
        escapeHtml(rec.direction || "web") +
        "</td>" +
        "<td>" +
        escapeHtml(rec.remote_phone || "—") +
        "</td>" +
        "<td>" +
        escapeHtml(rec.status) +
        "</td>" +
        "<td>" +
        escapeHtml(String(rec.duration)) +
        "</td>" +
        "<td>" +
        escapeHtml(formatDate(rec.created_at)) +
        "</td>" +
        "<td>" +
        (an ? escapeHtml(String(an.score)) : "—") +
        "</td>" +
        '<td class="calls-table__rec">' +
        (an ? escapeHtml(an.recommendations) : "—") +
        "</td>" +
        '<td class="calls-table__audio">' +
        audioCell +
        "</td>" +
        '<td class="calls-table__snippet">' +
        escapeHtml(snippet(rec.transcript_text, 280)) +
        "</td>";
      tbody.appendChild(tr);
    });

    tbody.querySelectorAll(".calls-table__btn-del").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-call-id");
        if (!id || !window.confirm("Удалить файл записи разговора? Строка в таблице останется.")) {
          return;
        }
        fetch(API_CALLS + "/" + encodeURIComponent(id) + "/recording", {
          method: "DELETE",
          credentials: "same-origin",
        })
          .then(function (r) {
            if (!r.ok) throw new Error("HTTP " + r.status);
            loadCalls();
          })
          .catch(function (e) {
            window.alert("Не удалось удалить: " + (e.message || String(e)));
          });
      });
    });
  }

  function loadCalls() {
    var tbody = document.getElementById("calls-tbody");
    if (!tbody) return;

    var trLoad = document.createElement("tr");
    trLoad.innerHTML =
      '<td colspan="10" class="calls-table__empty">Загрузка…</td>';
    while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
    tbody.appendChild(trLoad);

    fetch(API_CALLS, { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        renderCallsTable(data.items || []);
      })
      .catch(function (e) {
        while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
        var tr = document.createElement("tr");
        tr.innerHTML =
          '<td colspan="10" class="calls-table__empty calls-table__error">Не удалось загрузить данные: ' +
          escapeHtml(e.message || String(e)) +
          ". Проверьте, что бэкенд доступен через прокси <code>/api/</code>.</td>";
        tbody.appendChild(tr);
      });
  }

  function init() {
    setNavActive();
    loadCalls();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
