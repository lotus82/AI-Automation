/**
 * База знаний: список, загрузка txt/xlsx, удаление.
 */
(function () {
  "use strict";

  var API_LIST = "/api/knowledge/items";
  var API_UPLOAD = "/api/knowledge/upload";

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

  function setMsg(el, text, kind) {
    if (!el) return;
    el.textContent = text || "";
    el.className = "knowledge-upload__msg";
    if (kind === "err") el.classList.add("knowledge-upload__msg--err");
    if (kind === "ok") el.classList.add("knowledge-upload__msg--ok");
  }

  function renderList(container, rows) {
    if (!container) return;
    if (!rows || !rows.length) {
      container.innerHTML =
        '<p class="knowledge-list__empty">Пока нет записей. Загрузите .txt или .xlsx выше.</p>';
      return;
    }
    var thead =
      "<thead><tr>" +
      "<th>Заголовок</th>" +
      "<th>Фрагмент</th>" +
      "<th>Вектор</th>" +
      "<th>Дата</th>" +
      "<th></th>" +
      "</tr></thead>";
    var body = "<tbody>";
    var i;
    for (i = 0; i < rows.length; i++) {
      var r = rows[i];
      var emb = r.has_embedding
        ? '<span class="knowledge-badge knowledge-badge--ok">есть</span>'
        : '<span class="knowledge-badge knowledge-badge--warn">нет</span>';
      body +=
        "<tr data-id=\"" +
        escapeHtml(r.id) +
        "\">" +
        "<td class=\"knowledge-list__title\">" +
        escapeHtml(r.title) +
        "</td>" +
        "<td class=\"knowledge-list__preview\">" +
        escapeHtml(r.content_preview) +
        "</td>" +
        "<td>" +
        emb +
        "</td>" +
        "<td class=\"knowledge-list__date\">" +
        escapeHtml(formatDate(r.created_at)) +
        "</td>" +
        "<td><button type=\"button\" class=\"btn btn--danger btn--sm knowledge-del\">Удалить</button></td>" +
        "</tr>";
    }
    body += "</tbody>";
    container.innerHTML = '<table class="calls-table knowledge-table">' + thead + body + "</table>";
  }

  function loadList(container) {
    if (!container) return;
    container.textContent = "Загрузка…";
    fetch(API_LIST, { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        renderList(container, data);
      })
      .catch(function () {
        container.innerHTML =
          '<p class="knowledge-upload__msg knowledge-upload__msg--err">Не удалось загрузить список.</p>';
      });
  }

  function deleteRow(id, tr, listEl) {
    if (!confirm("Удалить этот фрагмент из базы знаний?")) return;
    fetch(API_LIST + "/" + encodeURIComponent(id), {
      method: "DELETE",
      credentials: "same-origin",
    })
      .then(function (r) {
        if (r.status === 204) return;
        if (r.status === 404) throw new Error("Уже удалено");
        throw new Error("HTTP " + r.status);
      })
      .then(function () {
        if (tr && tr.parentNode) tr.parentNode.removeChild(tr);
        if (listEl && !listEl.querySelector("tbody tr")) {
          renderList(listEl, []);
        }
      })
      .catch(function (e) {
        alert(e.message || "Ошибка удаления");
      });
  }

  function init() {
    var form = document.getElementById("knowledge-upload-form");
    var filesInput = document.getElementById("knowledge-files");
    var msg = document.getElementById("knowledge-upload-msg");
    var listEl = document.getElementById("knowledge-list");

    loadList(listEl);

    if (form && filesInput) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var files = filesInput.files;
        if (!files || !files.length) {
          setMsg(msg, "Выберите файлы.", "err");
          return;
        }
        var fd = new FormData();
        var j;
        for (j = 0; j < files.length; j++) {
          fd.append("files", files[j]);
        }
        setMsg(msg, "Загрузка и индексация…", "");
        var btn = document.getElementById("btn-knowledge-upload");
        if (btn) btn.disabled = true;
        fetch(API_UPLOAD, {
          method: "POST",
          body: fd,
          credentials: "same-origin",
        })
          .then(function (r) {
            return r.json().then(function (body) {
              return { ok: r.ok, status: r.status, body: body };
            });
          })
          .then(function (res) {
            if (!res.ok) {
              var det = res.body && res.body.detail;
              var text =
                typeof det === "string"
                  ? det
                  : Array.isArray(det)
                    ? det.map(function (x) {
                        return x.msg || x;
                      }).join("; ")
                    : "Ошибка " + res.status;
              throw new Error(text);
            }
            setMsg(
              msg,
              "Добавлено фрагментов: " + (res.body.created_count || 0) + ".",
              "ok",
            );
            filesInput.value = "";
            loadList(listEl);
          })
          .catch(function (e) {
            setMsg(msg, e.message || "Ошибка загрузки", "err");
          })
          .finally(function () {
            if (btn) btn.disabled = false;
          });
      });
    }

    if (listEl) {
      listEl.addEventListener("click", function (ev) {
        var t = ev.target;
        if (!t || !t.classList || !t.classList.contains("knowledge-del")) return;
        var tr = t.closest("tr");
        var id = tr && tr.getAttribute("data-id");
        if (id) deleteRow(id, tr, listEl);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
