/**
 * Расписание: CRUD и загрузка событий (CSV/JSON).
 */
(function () {
  "use strict";

  var API_LIST = "/api/schedules";
  var uploadTargetId = null;
  /** Последний загруженный список (для «Редактировать» без лишнего GET). */
  var cachedRows = null;

  function escapeHtml(s) {
    if (s == null) return "";
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function setMsg(el, text, kind) {
    if (!el) return;
    el.textContent = text || "";
    el.className = "knowledge-upload__msg";
    if (kind === "err") el.classList.add("knowledge-upload__msg--err");
    if (kind === "ok") el.classList.add("knowledge-upload__msg--ok");
  }

  function formatDt(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleString("ru-RU");
  }

  function toggleTypeFields() {
    var typeEl = document.getElementById("sch-type");
    var t = typeEl ? typeEl.value : "DATABASE";
    var intBlock = document.getElementById("sch-interval-block");
    var remBlock = document.getElementById("sch-reminder-block");
    var dbHint = document.getElementById("sch-db-hint");
    if (intBlock) intBlock.style.display = t === "INTERVAL" ? "flex" : "none";
    if (remBlock) remBlock.style.display = t === "REMINDER" ? "block" : "none";
    if (dbHint) dbHint.style.display = t === "DATABASE" ? "block" : "none";
  }

  function toggleEditTypeFields() {
    var typeEl = document.getElementById("sch-edit-type");
    var t = typeEl ? typeEl.value : "DATABASE";
    var intBlock = document.getElementById("sch-edit-interval-block");
    var remBlock = document.getElementById("sch-edit-reminder-block");
    var dbHint = document.getElementById("sch-edit-db-hint");
    if (intBlock) intBlock.style.display = t === "INTERVAL" ? "flex" : "none";
    if (remBlock) remBlock.style.display = t === "REMINDER" ? "block" : "none";
    if (dbHint) dbHint.style.display = t === "DATABASE" ? "block" : "none";
  }

  function patchSchedule(id, body) {
    return fetch(API_LIST + "/" + encodeURIComponent(id), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (res) {
      if (!res.ok) {
        return res.json().then(function (j) {
          var d = j && j.detail;
          var msg =
            typeof d === "string"
              ? d
              : d != null
                ? JSON.stringify(d)
                : "HTTP " + res.status;
          throw new Error(msg);
        });
      }
      return res.json();
    });
  }

  function openEditModal(r) {
    if (!r) return;
    document.getElementById("sch-edit-id").value = r.id || "";
    document.getElementById("sch-edit-chat-id").value = r.chat_id || "";
    var typeEl = document.getElementById("sch-edit-type");
    if (typeEl) typeEl.value = r.type || "DATABASE";
    var cb = document.getElementById("sch-edit-active");
    if (cb) cb.checked = !!r.is_active;
    var intv = r.interval_settings || {};
    var dEl = document.getElementById("sch-edit-days");
    var hEl = document.getElementById("sch-edit-hours");
    var mEl = document.getElementById("sch-edit-minutes");
    if (dEl) dEl.value = intv.days != null ? String(intv.days) : "0";
    if (hEl) hEl.value = intv.hours != null ? String(intv.hours) : "0";
    if (mEl) mEl.value = intv.minutes != null ? String(intv.minutes) : "0";
    var offEl = document.getElementById("sch-edit-offset");
    if (offEl)
      offEl.value =
        r.reminder_offset_minutes != null ? String(r.reminder_offset_minutes) : "0";
    document.getElementById("sch-edit-prompt").value = r.prompt != null ? r.prompt : "";
    document.getElementById("sch-edit-content").value =
      r.content_template != null ? r.content_template : "";
    setMsg(document.getElementById("sch-edit-msg"), "", null);
    toggleEditTypeFields();
    var bd = document.getElementById("sch-modal-backdrop");
    var md = document.getElementById("sch-edit-modal");
    if (bd) bd.hidden = false;
    if (md) md.hidden = false;
  }

  function closeEditModal() {
    var bd = document.getElementById("sch-modal-backdrop");
    var md = document.getElementById("sch-edit-modal");
    if (bd) bd.hidden = true;
    if (md) md.hidden = true;
  }

  function onEditSubmit(ev) {
    ev.preventDefault();
    var msgEl = document.getElementById("sch-edit-msg");
    var idEl = document.getElementById("sch-edit-id");
    var id = idEl && idEl.value;
    if (!id) return;
    var typeEl = document.getElementById("sch-edit-type");
    var t = typeEl ? typeEl.value : "DATABASE";
    var body = {
      chat_id: (document.getElementById("sch-edit-chat-id") || {}).value || "",
      is_active: !!(document.getElementById("sch-edit-active") || {}).checked,
      type: t,
      prompt: (document.getElementById("sch-edit-prompt") || {}).value || "",
      content_template: (document.getElementById("sch-edit-content") || {}).value || "",
      interval_settings: {},
      reminder_offset_minutes: null,
    };
    if (t === "INTERVAL") {
      body.interval_settings = {
        days: parseInt((document.getElementById("sch-edit-days") || {}).value || "0", 10) || 0,
        hours: parseInt((document.getElementById("sch-edit-hours") || {}).value || "0", 10) || 0,
        minutes: parseInt((document.getElementById("sch-edit-minutes") || {}).value || "0", 10) || 0,
      };
    }
    if (t === "REMINDER") {
      body.reminder_offset_minutes =
        parseInt((document.getElementById("sch-edit-offset") || {}).value || "0", 10) || 0;
    }
    setMsg(msgEl, "Сохранение…", null);
    patchSchedule(id, body)
      .then(function () {
        closeEditModal();
        return loadList();
      })
      .catch(function (e) {
        setMsg(msgEl, String(e.message || e), "err");
      });
  }

  function renderTable(tbody, rows) {
    if (!tbody) return;
    cachedRows = rows || [];
    if (!rows || !rows.length) {
      tbody.innerHTML =
        '<tr><td colspan="8" class="calls-table__empty">Нет расписаний. Создайте выше.</td></tr>';
      return;
    }
    var html = "";
    var i;
    for (i = 0; i < rows.length; i++) {
      var r = rows[i];
      var active = r.is_active ? "да" : "нет";
      var toggleLabel = r.is_active
        ? '<i class="fa-solid fa-pause" aria-hidden="true"></i> Приостановить'
        : '<i class="fa-solid fa-play" aria-hidden="true"></i> Запустить';
      var nextActive = r.is_active ? "false" : "true";
      html +=
        "<tr data-id=\"" +
        escapeHtml(r.id) +
        "\">" +
        "<td class=\"knowledge-list__preview\"><code>" +
        escapeHtml(r.id) +
        "</code></td>" +
        "<td>" +
        escapeHtml(r.chat_id) +
        "</td>" +
        "<td>" +
        escapeHtml(r.type) +
        "</td>" +
        "<td>" +
        active +
        "</td>" +
        "<td>" +
        formatDt(r.last_run_at) +
        "</td>" +
        "<td>" +
        '<button type="button" class="btn btn--secondary sch-toggle-btn" data-id="' +
        escapeHtml(r.id) +
        '" data-next-active="' +
        nextActive +
        '">' +
        toggleLabel +
        "</button>" +
        "</td>" +
        "<td>" +
        '<button type="button" class="btn btn--secondary sch-edit-btn" data-id="' +
        escapeHtml(r.id) +
        '"><i class="fa-solid fa-pen-to-square" aria-hidden="true"></i> Редактировать</button>' +
        "</td>" +
        "<td>" +
        '<button type="button" class="btn btn--secondary sch-upload-btn" data-id="' +
        escapeHtml(r.id) +
        '"><i class="fa-solid fa-file-arrow-up" aria-hidden="true"></i> Загрузить данные</button> ' +
        '<button type="button" class="btn btn--secondary sch-del-btn" data-id="' +
        escapeHtml(r.id) +
        '" title="Удалить"><i class="fa-solid fa-trash-can" aria-hidden="true"></i></button>' +
        "</td>" +
        "</tr>";
    }
    tbody.innerHTML = html;

    tbody.querySelectorAll(".sch-toggle-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var sid = btn.getAttribute("data-id");
        var na = btn.getAttribute("data-next-active") === "true";
        if (!sid) return;
        btn.disabled = true;
        patchSchedule(sid, { is_active: na })
          .then(function () {
            return loadList();
          })
          .catch(function (e) {
            window.alert("Ошибка: " + (e.message || e));
          })
          .finally(function () {
            btn.disabled = false;
          });
      });
    });

    tbody.querySelectorAll(".sch-edit-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var sid = btn.getAttribute("data-id");
        var j;
        var found = null;
        for (j = 0; j < cachedRows.length; j++) {
          if (String(cachedRows[j].id) === String(sid)) {
            found = cachedRows[j];
            break;
          }
        }
        if (found) openEditModal(found);
        else window.alert("Не найдена строка расписания.");
      });
    });

    tbody.querySelectorAll(".sch-upload-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        uploadTargetId = btn.getAttribute("data-id");
        var input = document.getElementById("sch-upload-input");
        if (input) input.click();
      });
    });
    tbody.querySelectorAll(".sch-del-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-id");
        if (!id || !window.confirm("Удалить это расписание и все события?")) return;
        fetch(API_LIST + "/" + encodeURIComponent(id), { method: "DELETE" })
          .then(function (res) {
            if (!res.ok) throw new Error("HTTP " + res.status);
            return loadList();
          })
          .catch(function (e) {
            window.alert("Ошибка удаления: " + (e.message || e));
          });
      });
    });
  }

  function loadList() {
    var tbody = document.getElementById("sch-tbody");
    return fetch(API_LIST)
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        renderTable(tbody, data);
      })
      .catch(function () {
        if (tbody) {
          tbody.innerHTML =
            '<tr><td colspan="8" class="calls-table__empty">Не удалось загрузить список.</td></tr>';
        }
      });
  }

  function onCreateSubmit(ev) {
    ev.preventDefault();
    var msgEl = document.getElementById("sch-form-msg");
    var typeEl = document.getElementById("sch-type");
    var t = typeEl ? typeEl.value : "DATABASE";
    var body = {
      chat_id: (document.getElementById("sch-chat-id") || {}).value || "",
      is_active: !!(document.getElementById("sch-active") || {}).checked,
      type: t,
      prompt: (document.getElementById("sch-prompt") || {}).value || "",
      content_template: (document.getElementById("sch-content") || {}).value || "",
      interval_settings: {},
      reminder_offset_minutes: null,
    };
    if (t === "INTERVAL") {
      body.interval_settings = {
        days: parseInt((document.getElementById("sch-days") || {}).value || "0", 10) || 0,
        hours: parseInt((document.getElementById("sch-hours") || {}).value || "0", 10) || 0,
        minutes: parseInt((document.getElementById("sch-minutes") || {}).value || "0", 10) || 0,
      };
    }
    if (t === "REMINDER") {
      body.reminder_offset_minutes =
        parseInt((document.getElementById("sch-offset") || {}).value || "0", 10) || 0;
    }

    setMsg(msgEl, "Сохранение…", null);
    fetch(API_LIST, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (j) {
            var d = j && j.detail;
            var msg =
              typeof d === "string"
                ? d
                : d != null
                  ? JSON.stringify(d)
                  : "HTTP " + res.status;
            throw new Error(msg);
          });
        }
        return res.json();
      })
      .then(function () {
        setMsg(msgEl, "Расписание создано.", "ok");
        var f = document.getElementById("schedule-create-form");
        if (f) f.reset();
        var cb = document.getElementById("sch-active");
        if (cb) cb.checked = true;
        toggleTypeFields();
        return loadList();
      })
      .catch(function (e) {
        setMsg(msgEl, String(e.message || e), "err");
      });
  }

  function onUploadChange(ev) {
    var input = ev.target;
    var file = input.files && input.files[0];
    if (!file || !uploadTargetId) {
      uploadTargetId = null;
      if (input) input.value = "";
      return;
    }
    var fd = new FormData();
    fd.append("file", file);
    fetch(
      API_LIST + "/" + encodeURIComponent(uploadTargetId) + "/upload-events",
      {
        method: "POST",
        body: fd,
      }
    )
      .then(function (res) {
        return res.json().then(function (j) {
          if (!res.ok) {
            var d = j && j.detail;
            var msg =
              typeof d === "string"
                ? d
                : d != null
                  ? JSON.stringify(d)
                  : "HTTP " + res.status;
            throw new Error(msg);
          }
          return j;
        });
      })
      .then(function (j) {
        window.alert("Импортировано событий: " + (j.imported != null ? j.imported : 0));
      })
      .catch(function (e) {
        window.alert("Ошибка загрузки: " + (e.message || e));
      })
      .finally(function () {
        uploadTargetId = null;
        if (input) input.value = "";
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var typeEl = document.getElementById("sch-type");
    if (typeEl) {
      typeEl.addEventListener("change", toggleTypeFields);
      toggleTypeFields();
    }
    var form = document.getElementById("schedule-create-form");
    if (form) form.addEventListener("submit", onCreateSubmit);
    var up = document.getElementById("sch-upload-input");
    if (up) up.addEventListener("change", onUploadChange);

    var editType = document.getElementById("sch-edit-type");
    if (editType) {
      editType.addEventListener("change", toggleEditTypeFields);
    }
    var editForm = document.getElementById("sch-edit-form");
    if (editForm) editForm.addEventListener("submit", onEditSubmit);
    var editClose = document.getElementById("sch-edit-close");
    var editCancel = document.getElementById("sch-edit-cancel");
    var editBackdrop = document.getElementById("sch-modal-backdrop");
    if (editClose) editClose.addEventListener("click", closeEditModal);
    if (editCancel) editCancel.addEventListener("click", closeEditModal);
    if (editBackdrop)
      editBackdrop.addEventListener("click", function () {
        closeEditModal();
      });

    loadList();
  });
})();
