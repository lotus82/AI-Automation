/**
 * Дашборд: список звонков и ОКК (GET /api/calls), транскрипт в модалке, удаление диалога и записи.
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

  function byId(id) {
    return document.getElementById(id);
  }

  function closeTranscriptModal() {
    var modal = byId("call-transcript-modal");
    var backdrop = byId("call-transcript-backdrop");
    if (modal) modal.hidden = true;
    if (backdrop) backdrop.hidden = true;
  }

  function openTranscriptModal(rec) {
    var modal = byId("call-transcript-modal");
    var backdrop = byId("call-transcript-backdrop");
    var meta = byId("call-transcript-meta");
    var body = byId("call-transcript-body");
    if (!modal || !body) return;
    var full = rec.transcript_text || "";
    if (meta) {
      meta.textContent =
        "Сессия: " +
        (rec.session_id || "—") +
        " · " +
        formatDate(rec.created_at);
    }
    body.textContent = full.trim() ? full : "Транскрипт пуст.";
    modal.hidden = false;
    if (backdrop) backdrop.hidden = false;
  }

  function bindTranscriptModal() {
    var closeBtn = byId("call-transcript-close");
    var backdrop = byId("call-transcript-backdrop");
    if (closeBtn) closeBtn.addEventListener("click", closeTranscriptModal);
    if (backdrop) backdrop.addEventListener("click", closeTranscriptModal);
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") closeTranscriptModal();
    });
  }

  function renderCallsTable(items) {
    var tbody = document.getElementById("calls-tbody");
    if (!tbody) return;

    while (tbody.firstChild) {
      tbody.removeChild(tbody.firstChild);
    }

    if (!items || items.length === 0) {
      var tr0 = document.createElement("tr");
      tr0.id = "calls-empty-row";
      tr0.innerHTML =
        '<td colspan="11" class="calls-table__empty">Пока нет записей. Завершите голосовой звонок или вызовите <code>POST /api/chat/finalize</code>.</td>';
      tbody.appendChild(tr0);
      return;
    }

    items.forEach(function (row) {
      var rec = row;
      var an = rec.analytics;
      var tr = document.createElement("tr");
      tr.className = "calls-table__row--clickable";
      var recUrl = API_CALLS + "/" + encodeURIComponent(rec.id) + "/recording";
      var audioCell = "—";
      if (rec.has_audio) {
        audioCell =
          '<div class="calls-audio-stack">' +
          '<audio controls preload="metadata" src="' +
          escapeHtml(recUrl) +
          '" class="calls-table__audio-el"></audio>' +
          '<div class="calls-audio-actions">' +
          '<a class="calls-table__btn-icon" href="' +
          escapeHtml(recUrl) +
          '" download title="Скачать запись"><i class="fa-solid fa-download" aria-hidden="true"></i></a>' +
          '<button type="button" class="calls-table__btn-icon calls-table__btn-icon--danger calls-table__btn-del-rec" data-call-id="' +
          escapeHtml(rec.id) +
          '" title="Удалить только файл записи" aria-label="Удалить файл записи"><i class="fa-solid fa-file-circle-xmark" aria-hidden="true"></i></button>' +
          "</div></div>";
      }
      var recShort = an ? snippet(an.recommendations, 100) : "—";
      var recCell =
        an && an.recommendations
          ? '<span class="calls-table__rec calls-table__rec--compact">' +
            escapeHtml(recShort) +
            "</span>"
          : "—";
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
        recCell +
        "</td>" +
        '<td class="calls-table__audio">' +
        audioCell +
        "</td>" +
        '<td class="calls-table__snippet">' +
        escapeHtml(snippet(rec.transcript_text, 120)) +
        "</td>" +
        '<td class="calls-table__actions">' +
        '<button type="button" class="calls-table__btn-row-del calls-table__btn-del-call" data-call-id="' +
        escapeHtml(rec.id) +
        '" title="Удалить диалог целиком"><i class="fa-solid fa-trash-can" aria-hidden="true"></i></button>' +
        "</td>";
      tbody.appendChild(tr);
      if (an && an.recommendations) {
        var recTip = tr.querySelector(".calls-table__rec--compact");
        if (recTip) recTip.setAttribute("title", an.recommendations);
      }

      tr.addEventListener("click", function (ev) {
        if (ev.target.closest("a, button, audio, label, input, select, textarea")) {
          return;
        }
        openTranscriptModal(rec);
      });
    });

    tbody.querySelectorAll(".calls-table__audio-el").forEach(function (audioEl) {
      try {
        audioEl.load();
      } catch (e) {}
    });

    tbody.querySelectorAll(".calls-table__btn-del-rec").forEach(function (btn) {
      btn.addEventListener("click", function (ev) {
        ev.stopPropagation();
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

    tbody.querySelectorAll(".calls-table__btn-del-call").forEach(function (btn) {
      btn.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var id = btn.getAttribute("data-call-id");
        if (!id || !window.confirm("Удалить этот диалог целиком из базы? Действие необратимо.")) {
          return;
        }
        fetch(API_CALLS + "/" + encodeURIComponent(id), {
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
      '<td colspan="11" class="calls-table__empty">Загрузка…</td>';
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
          '<td colspan="11" class="calls-table__empty calls-table__error">Не удалось загрузить данные: ' +
          escapeHtml(e.message || String(e)) +
          ". Проверьте, что бэкенд доступен через прокси <code>/api/</code>.</td>";
        tbody.appendChild(tr);
      });
  }

  function init() {
    bindTranscriptModal();
    loadCalls();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
