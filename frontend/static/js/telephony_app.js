/**
 * Загрузка очереди автообзвона и старт Celery-кампании.
 * TODO: Отображать последний ответ API в виде уведомления (toast).
 */
(function () {
  "use strict";

  var API_UPLOAD = "/api/dialer/queue/upload";
  var API_START = "/api/dialer/campaign/start";

  function setNavActive() {
    var path = window.location.pathname.replace(/\/$/, "") || "/";
    document.querySelectorAll(".nav__link[data-nav]").forEach(function (a) {
      var key = a.getAttribute("data-nav");
      var active =
        (key === "telephony" && path.indexOf("telephony") !== -1) ||
        (key === "scenarios" && path.indexOf("scenarios") !== -1) ||
        (key === "tester" && path.indexOf("tester") !== -1) ||
        (key === "settings" && path.indexOf("settings") !== -1) ||
        (key === "knowledge" && path.indexOf("knowledge") !== -1) ||
        (key === "home" && (path === "/" || path.endsWith("/index.html")));
      a.classList.toggle("nav__link--active", active);
    });
  }

  function initUpload() {
    var form = document.getElementById("upload-form");
    var msg = document.getElementById("upload-msg");
    var input = document.getElementById("phones-file");
    if (!form || !input) return;
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
    setNavActive();
    initUpload();
    initCampaign();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
