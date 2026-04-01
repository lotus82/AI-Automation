/**
 * Форма создания сценария и список GET /api/scenarios.
 * TODO: Показать даты создания и id UUID в компактном виде.
 */
(function () {
  "use strict";

  var API = "/api/scenarios";

  function escapeHtml(s) {
    if (s == null) return "";
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function renderList(items) {
    var box = document.getElementById("scenario-list");
    if (!box) return;
    if (!items || !items.length) {
      box.innerHTML = "<p>Пока нет сценариев.</p>";
      return;
    }
    var html = '<ul class="nav" style="list-style:disc;padding-left:1.25rem;">';
    var i;
    for (i = 0; i < items.length; i++) {
      var it = items[i];
      html +=
        "<li style=\"margin-bottom:0.75rem;\"><strong>" +
        escapeHtml(it.title) +
        "</strong><br/><code style=\"font-size:0.75rem;\">" +
        escapeHtml(it.id) +
        "</code></li>";
    }
    html += "</ul>";
    box.innerHTML = html;
  }

  function loadList() {
    var box = document.getElementById("scenario-list");
    if (box) box.textContent = "Загрузка…";
    fetch(API, { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(renderList)
      .catch(function (e) {
        if (box) box.textContent = "Ошибка загрузки: " + (e.message || e);
      });
  }

  function initForm() {
    var form = document.getElementById("scenario-form");
    var msg = document.getElementById("scenario-form-msg");
    if (!form) return;
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var title = document.getElementById("sc-title");
      var persona = document.getElementById("sc-persona");
      var objections = document.getElementById("sc-objections");
      if (!title || !persona || !objections) return;
      var body = {
        title: title.value.trim(),
        client_persona_prompt: persona.value.trim(),
        objections_to_raise: objections.value.trim(),
      };
      if (msg) msg.textContent = "Отправка…";
      fetch(API, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
        .then(function (r) {
          if (!r.ok) return r.text().then(function (t) {
            throw new Error(t || "HTTP " + r.status);
          });
          return r.json();
        })
        .then(function () {
          if (msg) msg.textContent = "Сценарий сохранён.";
          form.reset();
          loadList();
        })
        .catch(function (e) {
          if (msg) msg.textContent = "Ошибка: " + (e.message || e);
        });
    });
  }

  function fixNavScenarios() {
    var path = window.location.pathname.replace(/\/$/, "") || "/";
    document.querySelectorAll(".nav__link[data-nav]").forEach(function (a) {
      var key = a.getAttribute("data-nav");
      var active =
        (key === "scenarios" && path.indexOf("scenarios") !== -1) ||
        (key === "telephony" && path.indexOf("telephony") !== -1) ||
        (key === "tester" && path.indexOf("tester") !== -1) ||
        (key === "home" && (path === "/" || path.endsWith("/index.html")));
      a.classList.toggle("nav__link--active", active);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      fixNavScenarios();
      initForm();
      loadList();
    });
  } else {
    fixNavScenarios();
    initForm();
    loadList();
  }
})();
