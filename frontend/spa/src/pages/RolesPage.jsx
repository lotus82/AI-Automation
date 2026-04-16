import { useCallback, useEffect, useState } from "react";
import api from "../api/client.js";
import { IconDeleteButton } from "../components/ui/IconActionButtons.jsx";
import { SK } from "../constants/systemSettingsKeys.js";
import { mapFromList } from "../utils/systemSettingsForm.js";

function newRowId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    try {
      return crypto.randomUUID();
    } catch {
      /* ignore */
    }
  }
  return `r-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function parseRolesFromMap(map) {
  const raw = map[SK.SYSTEM_ROLES_CONFIG]?.value;
  if (raw != null && String(raw).trim()) {
    try {
      const o = JSON.parse(String(raw));
      if (o.roles && Array.isArray(o.roles) && o.roles.length > 0) {
        const defId = String(o.default_role_id || o.roles[0].id || "");
        let anId =
          o.analyst_role_id != null && String(o.analyst_role_id).trim()
            ? String(o.analyst_role_id)
            : defId;
        if (!o.roles.some((r) => String(r.id) === anId)) anId = defId;
        return {
          defaultRoleId: defId || String(o.roles[0].id),
          analystRoleId: anId,
          roleRows: o.roles.map((r) => ({
            rowKey: newRowId(),
            roleId: String(r.id),
            name: String(r.name || ""),
            prompt: String(r.prompt || ""),
          })),
        };
      }
    } catch {
      /* seed from legacy keys */
    }
  }
  const c = map[SK.DEFAULT_CONSULTANT_PROMPT]?.value ?? "";
  const a = map[SK.ANALYST_QA_PROMPT]?.value ?? "";
  const r1 = newRowId();
  const r2 = newRowId();
  return {
    defaultRoleId: r1,
    analystRoleId: r2,
    roleRows: [
      { rowKey: newRowId(), roleId: r1, name: "Консультант", prompt: String(c) },
      { rowKey: newRowId(), roleId: r2, name: "ОКК", prompt: String(a) },
    ],
  };
}

function parseMaxGroupRowsFromMap(map) {
  const raw = map[SK.MAX_GROUP_CHAT_PROMPTS]?.value;
  if (raw != null && String(raw).trim()) {
    try {
      const o = JSON.parse(String(raw));
      if (o && typeof o === "object" && !Array.isArray(o)) {
        const entries = Object.entries(o);
        if (entries.length > 0) {
          return entries.map(([chatId, val]) => {
            let roleId = "";
            let additionalPrompt = "";
            if (typeof val === "string") {
              additionalPrompt = val;
            } else if (val && typeof val === "object") {
              additionalPrompt = typeof val.additional_prompt === "string" ? val.additional_prompt : "";
              roleId = val.role_id != null && String(val.role_id).trim() ? String(val.role_id) : "";
            }
            const description =
              val && typeof val === "object" && typeof val.description === "string" ? val.description : "";
            return {
              rowId: newRowId(),
              chatId: String(chatId),
              description,
              roleId,
              additionalPrompt,
            };
          });
        }
      }
    } catch {
      /* fallback legacy */
    }
  }
  const legacyId =
    map[SK.MAX_GROUP_CHAT_ID]?.value != null ? String(map[SK.MAX_GROUP_CHAT_ID].value).trim() : "";
  const legacyPrompt =
    map[SK.MAX_GROUP_ADDITIONAL_PROMPT]?.value != null ? String(map[SK.MAX_GROUP_ADDITIONAL_PROMPT].value) : "";
  if (legacyId) {
    return [
      {
        rowId: newRowId(),
        chatId: legacyId,
        description: "",
        roleId: "",
        additionalPrompt: legacyPrompt,
      },
    ];
  }
  return [];
}

function initialTextForm() {
  return { textBotSupplement: "" };
}

export function RolesPage() {
  const [form, setForm] = useState(initialTextForm);
  const [roleRows, setRoleRows] = useState([]);
  const [defaultRoleId, setDefaultRoleId] = useState("");
  const [analystRoleId, setAnalystRoleId] = useState("");
  const [maxGroupRows, setMaxGroupRows] = useState([]);
  const [statusMsg, setStatusMsg] = useState("");
  const [statusError, setStatusError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const applyMap = useCallback((map) => {
    const pr = parseRolesFromMap(map);
    setDefaultRoleId(pr.defaultRoleId);
    setAnalystRoleId(pr.analystRoleId);
    setRoleRows(pr.roleRows);
    setForm({
      textBotSupplement:
        map[SK.TEXT_BOT_SYSTEM_SUPPLEMENT]?.value != null
          ? String(map[SK.TEXT_BOT_SYSTEM_SUPPLEMENT].value)
          : "",
    });
    setMaxGroupRows(parseMaxGroupRowsFromMap(map));
  }, []);

  const loadSettings = useCallback(async () => {
    setStatusMsg("Загрузка…");
    setStatusError(false);
    try {
      const { data: rows } = await api.get("/settings");
      applyMap(mapFromList(rows));
      setStatusMsg("Настройки загружены.");
      setStatusError(false);
    } catch (e) {
      console.error(e);
      const msg = e?.response?.data?.detail ?? e?.message ?? String(e);
      setStatusMsg(`Не удалось загрузить: ${msg}`);
      setStatusError(true);
    } finally {
      setLoading(false);
    }
  }, [applyMap]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const setField = (key, value) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  const updateRoleRow = (rowKey, patch) => {
    setRoleRows((rows) => rows.map((r) => (r.rowKey === rowKey ? { ...r, ...patch } : r)));
  };

  const removeRoleRow = (rowKey) => {
    const victim = roleRows.find((r) => r.rowKey === rowKey);
    const next = roleRows.filter((r) => r.rowKey !== rowKey);
    setRoleRows(next);
    if (!victim || next.length === 0) return;
    if (defaultRoleId === victim.roleId) {
      setDefaultRoleId(next[0].roleId);
    }
    if (analystRoleId === victim.roleId) {
      setAnalystRoleId(next[0].roleId);
    }
    setMaxGroupRows((gr) => gr.map((g) => (g.roleId === victim.roleId ? { ...g, roleId: "" } : g)));
  };

  const addRoleRow = () => {
    const rid = newRowId();
    setRoleRows((rows) => [...rows, { rowKey: newRowId(), roleId: rid, name: "", prompt: "" }]);
    if (roleRows.length === 0) {
      setDefaultRoleId(rid);
      setAnalystRoleId(rid);
    }
  };

  const updateMaxRow = (rowId, patch) => {
    setMaxGroupRows((rows) => rows.map((r) => (r.rowId === rowId ? { ...r, ...patch } : r)));
  };

  const removeMaxRow = (rowId) => {
    setMaxGroupRows((rows) => rows.filter((r) => r.rowId !== rowId));
  };

  const addMaxRow = () => {
    setMaxGroupRows((rows) => [
      ...rows,
      { rowId: newRowId(), chatId: "", description: "", roleId: "", additionalPrompt: "" },
    ]);
  };

  const collectPayload = () => {
    const idSet = new Set(roleRows.map((r) => r.roleId));
    if (!idSet.has(defaultRoleId)) {
      throw new Error("Выберите основную роль из списка (или добавьте роль).");
    }
    if (!idSet.has(analystRoleId)) {
      throw new Error("Выберите роль для ОКК из списка.");
    }
    const rolesConfig = {
      default_role_id: defaultRoleId,
      analyst_role_id: analystRoleId,
      roles: roleRows.map((r) => ({
        id: r.roleId,
        name: (r.name || "").trim(),
        prompt: r.prompt ?? "",
      })),
    };
    const groupMap = {};
    for (const r of maxGroupRows) {
      const cid = (r.chatId || "").trim();
      if (!cid) continue;
      groupMap[cid] = {
        role_id: (r.roleId || "").trim() || null,
        additional_prompt: r.additionalPrompt ?? "",
        description: (r.description || "").trim(),
      };
    }
    return {
      [SK.SYSTEM_ROLES_CONFIG]: JSON.stringify(rolesConfig),
      [SK.MAX_GROUP_CHAT_PROMPTS]: JSON.stringify(groupMap),
      [SK.TEXT_BOT_SYSTEM_SUPPLEMENT]: form.textBotSupplement,
    };
  };

  const onSubmit = async (ev) => {
    ev.preventDefault();
    if (roleRows.length === 0) {
      setStatusMsg("Добавьте хотя бы одну роль.");
      setStatusError(true);
      return;
    }
    let payload;
    try {
      payload = collectPayload();
    } catch (err) {
      setStatusMsg(err?.message ?? String(err));
      setStatusError(true);
      return;
    }
    setSaving(true);
    setStatusMsg("Сохранение…");
    setStatusError(false);
    try {
      await api.put("/settings", { values: payload });
      setStatusMsg("Сохранено.");
      setStatusError(false);
      await loadSettings();
    } catch (e) {
      console.error(e);
      const body =
        typeof e?.response?.data === "string"
          ? e.response.data
          : e?.response?.data != null
            ? JSON.stringify(e.response.data)
            : e?.message ?? String(e);
      setStatusMsg(`Ошибка сохранения: ${body}`);
      setStatusError(true);
    } finally {
      setSaving(false);
    }
  };

  const inputClass =
    "w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500";
  const labelClass = "mb-1 block text-sm font-medium text-slate-200";
  const helpClass = "mt-0 text-sm text-slate-400";
  const sectionClass =
    "mb-8 rounded-xl border border-slate-700/80 bg-slate-800/40 p-5 shadow-sm";
  const sectionTitleClass =
    "mb-4 flex items-center gap-2 text-lg font-semibold text-slate-100";

  const roleOptions = roleRows.map((r) => ({
    value: r.roleId,
    label: (r.name || "").trim() || r.roleId.slice(0, 8) + "…",
  }));

  return (
    <div className="w-full min-w-0 text-slate-100">
      <h1 className="mb-2 flex items-center gap-2 text-2xl font-bold text-white">
        <span className="text-slate-300" aria-hidden>
          🎭
        </span>
        Роли и промпты
      </h1>
      <p className="mb-4 text-sm leading-relaxed text-slate-300">
        Роли с системными промптами, привязка групп MAX к роли и доп. тексту, общее дополнение для текстовых чатов. Хранится
        в <code className="rounded bg-slate-800 px-1 text-xs">system_settings</code>.
      </p>

      <p
        className={`mb-4 min-h-[1.25rem] text-sm ${statusError ? "text-red-400" : "text-emerald-400"}`}
        aria-live="polite"
      >
        {statusMsg}
      </p>

      {loading ? (
        <p className="text-slate-400">Загрузка…</p>
      ) : (
        <form className="space-y-2" onSubmit={onSubmit}>
          <section className={sectionClass} aria-labelledby="roles-table-title">
            <h2 id="roles-table-title" className={sectionTitleClass}>
              <span aria-hidden>👤</span> Системные роли
            </h2>
            <p className={`${helpClass} mb-3`}>
              Основная роль по умолчанию используется в чате и расписании, если для группы MAX не выбрана другая. Роль для
              ОКК — промпт анализа качества диалогов (сценарий QA).
            </p>
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
              <div>
                <label className={labelClass} htmlFor="analyst-role-select">
                  Роль для ОКК / аналитики
                </label>
                <select
                  id="analyst-role-select"
                  className={`${inputClass} max-w-md`}
                  value={analystRoleId}
                  onChange={(e) => setAnalystRoleId(e.target.value)}
                >
                  {roleOptions.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="overflow-x-auto rounded-lg border border-slate-700/80">
              <table className="w-full min-w-[640px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-700 bg-slate-900/60 text-xs uppercase text-slate-400">
                    <th className="px-2 py-2 w-28 text-center font-medium">По умолчанию</th>
                    <th className="px-3 py-2 font-medium w-[10rem]">Название</th>
                    <th className="px-3 py-2 font-medium">Системный промпт</th>
                    <th className="px-2 py-2 w-24 text-right"> </th>
                  </tr>
                </thead>
                <tbody>
                  {roleRows.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-3 py-4 text-slate-500">
                        Нет ролей. Нажмите «Добавить роль».
                      </td>
                    </tr>
                  ) : (
                    roleRows.map((row) => (
                      <tr key={row.rowKey} className="border-b border-slate-800 align-top">
                        <td className="px-2 py-2 text-center">
                          <input
                            type="radio"
                            name="default-role"
                            className="h-4 w-4 accent-emerald-500"
                            checked={defaultRoleId === row.roleId}
                            onChange={() => setDefaultRoleId(row.roleId)}
                            aria-label={`Основная роль: ${row.name || row.roleId}`}
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="text"
                            className={inputClass}
                            placeholder="Например: Консультант"
                            value={row.name}
                            onChange={(e) => updateRoleRow(row.rowKey, { name: e.target.value })}
                            aria-label="Название роли"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <textarea
                            className={`${inputClass} resize-y min-h-[6rem]`}
                            rows={5}
                            value={row.prompt}
                            onChange={(e) => updateRoleRow(row.rowKey, { prompt: e.target.value })}
                            aria-label="Системный промпт роли"
                          />
                        </td>
                        <td className="px-2 py-2 text-right whitespace-nowrap">
                          <IconDeleteButton
                            title="Удалить роль"
                            disabled={roleRows.length <= 1}
                            onClick={() => removeRoleRow(row.rowKey)}
                          />
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <button
              type="button"
              className="mt-3 rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700"
              onClick={addRoleRow}
            >
              + Добавить роль
            </button>
          </section>

          <section className={sectionClass} aria-labelledby="max-groups-title">
            <h2 id="max-groups-title" className={sectionTitleClass}>
              <span aria-hidden>💬</span> Групповые чаты MAX
            </h2>
            <p className={`${helpClass} mb-3`}>
              Для каждой группы: <strong>роль</strong> (базовый системный промпт) и при необходимости{" "}
              <strong>дополнительный текст</strong> только для этого чата. Пустая роль в списке — используется основная
              роль по умолчанию. Совпадение по <code className="text-xs text-slate-300">session_id</code> /{" "}
              <code className="text-xs text-slate-300">chat_id</code>.
            </p>
            <div className="overflow-x-auto rounded-lg border border-slate-700/80">
              <table className="w-full min-w-[880px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-700 bg-slate-900/60 text-xs uppercase text-slate-400">
                    <th className="px-3 py-2 font-medium w-[11rem]">ID группы</th>
                    <th className="px-3 py-2 font-medium min-w-[10rem]">Описание</th>
                    <th className="px-3 py-2 font-medium w-[12rem]">Роль</th>
                    <th className="px-3 py-2 font-medium">Доп. промпт для группы</th>
                    <th className="px-2 py-2 w-24 text-right"> </th>
                  </tr>
                </thead>
                <tbody>
                  {maxGroupRows.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-3 py-4 text-slate-500">
                        Нет записей. Нажмите «Добавить группу».
                      </td>
                    </tr>
                  ) : (
                    maxGroupRows.map((row) => (
                      <tr key={row.rowId} className="border-b border-slate-800 align-top">
                        <td className="px-3 py-2">
                          <input
                            type="text"
                            className={inputClass}
                            placeholder="-1001234567890"
                            autoComplete="off"
                            value={row.chatId}
                            onChange={(e) => updateMaxRow(row.rowId, { chatId: e.target.value })}
                            aria-label="ID группы MAX"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="text"
                            className={inputClass}
                            placeholder="Например: чат отдела продаж"
                            autoComplete="off"
                            value={row.description ?? ""}
                            onChange={(e) => updateMaxRow(row.rowId, { description: e.target.value })}
                            aria-label="Описание группового чата"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <select
                            className={inputClass}
                            value={row.roleId}
                            onChange={(e) => updateMaxRow(row.rowId, { roleId: e.target.value })}
                            aria-label="Роль для группы"
                          >
                            <option value="">— основная по умолчанию —</option>
                            {roleOptions.map((o) => (
                              <option key={o.value} value={o.value}>
                                {o.label}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="px-3 py-2">
                          <textarea
                            className={`${inputClass} resize-y min-h-[5rem]`}
                            rows={4}
                            value={row.additionalPrompt}
                            onChange={(e) => updateMaxRow(row.rowId, { additionalPrompt: e.target.value })}
                            aria-label="Дополнительный промпт"
                          />
                        </td>
                        <td className="px-2 py-2 text-right whitespace-nowrap">
                          <IconDeleteButton
                            title="Удалить строку группы"
                            onClick={() => removeMaxRow(row.rowId)}
                          />
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <button
              type="button"
              className="mt-3 rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700"
              onClick={addMaxRow}
            >
              + Добавить группу
            </button>
          </section>

          <section className={sectionClass} aria-labelledby="messenger-supplement-title">
            <h2 id="messenger-supplement-title" className={sectionTitleClass}>
              <span aria-hidden>📱</span> Мессенджеры и текстовые чаты
            </h2>
            <div className="mb-0">
              <label className={labelClass} htmlFor="text-bot-supplement">
                Дополнение к системному промпту (TEXT_BOT_SYSTEM_SUPPLEMENT)
              </label>
              <p className={helpClass}>
                Добавляется <strong>после</strong> промпта роли, CRM и доп. текста группы MAX. Используется во{" "}
                <strong>всех текстовых чатах</strong> с моделью: мессенджеры (MAX и др.), встроенный чат панели, чат
                врача с ИИ в МИС, проактивные сообщения по расписанию и аналогичные сценарии — для единых правил формата
                ответа (тон, длина, обращение).
              </p>
              <textarea
                id="text-bot-supplement"
                className={`${inputClass} resize-y`}
                rows={5}
                placeholder='Например: Отвечай кратко, до 800 символов. Обращайся на «вы». Не используй Markdown.'
                value={form.textBotSupplement}
                onChange={(e) => setField("textBotSupplement", e.target.value)}
              />
            </div>
          </section>

          <div className="mt-6">
            <button
              type="submit"
              className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-medium text-white shadow hover:bg-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 disabled:opacity-50"
              disabled={saving}
            >
              💾 Сохранить
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
