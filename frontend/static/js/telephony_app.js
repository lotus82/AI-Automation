/**
 * Загрузка очереди автообзвона и старт Celery-кампании.
 * TODO: Отображать последний ответ API в виде уведомления (toast).
 */
(function () {
  "use strict";

  var API_UPLOAD = "/api/dialer/queue/upload";
  var API_START = "/api/dialer/campaign/start";

  function initUpload() {
    var form = document.getElementById("upload-form");
    var msg = document.getElementById("upload-msg");
    var input = document.getElementById("phones-file");
    var nameEl = document.getElementById("phones-file-name");
    if (!form || !input) return;

    function syncName() {
      if (!nameEl) return;
      var f = input.files && input.files[0];
      nameEl.textContent = f ? f.name : "Файл не выбран";
    }
    input.addEventListener("change", syncName);
    syncName();

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      if (!input.files || !input.files[0]) return;
      var fd = new FormData();
      fd.append("file", input.files[0]);
      if (msg) msg.textContent = "Загрузка…";
      fetch(API_UPLOAD, {
        method: "POST",
        body: fd,
        credentials: "same-origin",
      })
        .then(function (r) {
          if (!r.ok) return r.text().then(function (t) {
            throw new Error(t || "HTTP " + r.status);
          });
          return r.json();
        })
        .then(function (data) {
          if (msg) msg.textContent = "Добавлено номеров: " + (data.inserted != null ? data.inserted : "?");
          input.value = "";
          syncName();
        })
        .catch(function (e) {
          if (msg) msg.textContent = "Ошибка: " + (e.message || e);
        });
    });
  }

  function initCampaign() {
    var btn = document.getElementById("btn-campaign");
    var msg = document.getElementById("campaign-msg");
    if (!btn) return;
    btn.addEventListener("click", function () {
      if (msg) msg.textContent = "Отправка…";
      fetch(API_START, { method: "POST", credentials: "same-origin" })
        .then(function (r) {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        })
        .then(function (data) {
          if (msg) msg.textContent = "Статус: " + (data.status || "ok");
        })
        .catch(function (e) {
          if (msg) msg.textContent = "Ошибка: " + (e.message || e);
        });
    });
  }

  function init() {
    initUpload();
    initCampaign();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
