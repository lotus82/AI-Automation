/**
 * Подсветка пункта меню на странице тестера (без загрузки таблицы звонков).
 */
(function () {
  "use strict";
  var path = window.location.pathname.replace(/\/$/, "") || "/";
  document.querySelectorAll(".nav__link[data-nav]").forEach(function (a) {
    var key = a.getAttribute("data-nav");
    var active =
      (key === "tester" && path.indexOf("tester") !== -1) ||
      (key === "telephony" && path.indexOf("telephony") !== -1) ||
      (key === "scenarios" && path.indexOf("scenarios") !== -1) ||
      (key === "settings" && path.indexOf("settings") !== -1) ||
      (key === "home" && (path === "/" || path.endsWith("/index.html")));
    a.classList.toggle("nav__link--active", active);
  });
})();
