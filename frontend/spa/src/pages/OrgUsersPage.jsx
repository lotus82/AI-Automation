import { Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import api from "../api/client.js";
import { useAuthStore } from "../store/authStore.js";
import { BTN_SAVE_COMPACT, ICON_BTN } from "../styles/pageLayout.js";

/** Текст ошибки FastAPI (detail: string | { msg }[]). */
function formatApiDetail(d) {
  if (d == null) return "";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) return String(item.msg);
        return JSON.stringify(item);
      })
      .filter(Boolean)
      .join("; ");
  }
  if (typeof d === "object") return d.message ? String(d.message) : JSON.stringify(d);
  return String(d);
}

const SECTION_OPTIONS = [
  { id: "qa-analytics", label: "QA-аналитика" },
  { id: "ai-trainer", label: "ИИ-тренер" },
  { id: "leadgen", label: "ИИ-лидогенератор" },
  { id: "questionnaires", label: "Опросники" },
  { id: "forms", label: "Формы" },
  { id: "shops", label: "Магазины" },
  { id: "mis", label: "МИС" },
  { id: "integrations", label: "Интеграции" },
  { id: "roles", label: "Роли" },
  { id: "settings", label: "Настройки" },
  { id: "logs", label: "Логи" },
  { id: "knowledge", label: "База знаний" },
  { id: "schedule", label: "Расписание" },
];

function roleLabel(role) {
  const m = {
    super_admin: "Главный админ",
    org_admin: "Админ организации",
    director: "Директор",
    employee: "Сотрудник",
  };
  return m[role] || role;
}

export function OrgUsersPage() {
  const user = useAuthStore((s) => s.user);
  const canManage = user?.role === "org_admin" || user?.role === "director";
  const isOrgAdmin = user?.role === "org_admin";

  const [rows, setRows] = useState([]);
  /** portal_user_id пользователей, у которых уже есть профиль врача МИС */
  const [misDoctorPortalIds, setMisDoctorPortalIds] = useState(() => new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [cuUser, setCuUser] = useState("");
  const [cuPass, setCuPass] = useState("");
  const [cuName, setCuName] = useState("");
  const [cuRole, setCuRole] = useState("employee");
  const [cuSections, setCuSections] = useState(["qa-analytics"]);
  const [creating, setCreating] = useState(false);
  const [formMsg, setFormMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const usersReq = api.get("/portal/users");
      const doctorsReq =
        user?.role === "org_admin"
          ? api.get("/mis/admin/doctors").catch(() => ({ data: [] }))
          : Promise.resolve({ data: [] });
      const [{ data }, doctorsRes] = await Promise.all([usersReq, doctorsReq]);
      setRows(Array.isArray(data) ? data : []);
      const ids = new Set(
        (Array.isArray(doctorsRes.data) ? doctorsRes.data : []).map((d) => String(d.portal_user_id)),
      );
      setMisDoctorPortalIds(ids);
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
      setRows([]);
      setMisDoctorPortalIds(new Set());
    } finally {
      setLoading(false);
    }
  }, [user?.role]);

  useEffect(() => {
    if (canManage) load();
  }, [canManage, load]);

  if (!canManage) {
    return <Navigate to="/scenarios/qa-analytics" replace />;
  }

  const toggleSection = (arr, id, on) => {
    if (on) return arr.includes(id) ? arr : [...arr, id];
    return arr.filter((x) => x !== id);
  };

  const onCreate = async (e) => {
    e.preventDefault();
    if (user.role === "director" && cuRole !== "employee") {
      setFormMsg("Директор может создавать только сотрудников");
      return;
    }
    setFormMsg("");
    setCreating(true);
    try {
      await api.post("/portal/users", {
        username: cuUser.trim(),
        password: cuPass,
        display_name: cuName.trim() || null,
        role: cuRole,
        sections: cuRole === "employee" ? cuSections : cuRole === "director" ? cuSections : [],
      });
      setCuUser("");
      setCuPass("");
      setCuName("");
      setCuRole("employee");
      setCuSections(["qa-analytics"]);
      setFormMsg("Пользователь создан.");
      await load();
    } catch (err) {
      setFormMsg(formatApiDetail(err?.response?.data?.detail) || "Ошибка создания");
    } finally {
      setCreating(false);
    }
  };

  const onResetPassword = async (id, username) => {
    const np = window.prompt(`Новый пароль для «${username}» (мин. 6 символов):`);
    if (np == null || np.length < 6) return;
    try {
      await api.post(`/portal/users/${id}/password`, { new_password: np });
      window.alert("Пароль обновлён.");
    } catch (err) {
      window.alert(err?.response?.data?.detail ?? err?.message ?? "Ошибка");
    }
  };

  const onToggleActive = async (row) => {
    if (row.id === user.id) {
      window.alert("Нельзя отключить самого себя.");
      return;
    }
    try {
      await api.patch(`/portal/users/${row.id}`, { is_active: !row.is_active });
      await load();
    } catch (err) {
      window.alert(err?.response?.data?.detail ?? err?.message ?? "Ошибка");
    }
  };

  const onSaveSections = async (row, sections) => {
    try {
      await api.patch(`/portal/users/${row.id}`, { sections });
      await load();
    } catch (err) {
      window.alert(err?.response?.data?.detail ?? err?.message ?? "Ошибка");
    }
  };

  const onAssignMisDoctor = async (row) => {
    const q = window.prompt(
      `Специализация / должность для «${row.username}» (можно оставить пустым):`,
      "",
    );
    if (q === null) return;
    try {
      await api.post("/mis/admin/doctors", {
        portal_user_id: row.id,
        qualification: String(q).trim(),
      });
      setMisDoctorPortalIds((prev) => new Set(prev).add(String(row.id)));
      window.alert(
        "Пользователь назначен врачом МИС. При необходимости включите раздел «МИС» в правах доступа ниже.",
      );
    } catch (err) {
      window.alert(formatApiDetail(err?.response?.data?.detail) || err?.message || "Ошибка");
    }
  };

  return (
    <div className="w-full min-w-0 space-y-8 text-slate-100">
      <div>
        <h1 className="text-2xl font-bold text-white">Пользователи организации</h1>
      </div>

      <section className="rounded-xl border border-slate-700/80 bg-slate-900/40 p-6">
        <h2 className="text-lg font-semibold text-slate-200">Новый пользователь</h2>
        <form className="mt-4 space-y-4" onSubmit={onCreate}>
          {formMsg ? <p className="text-sm text-emerald-400">{formMsg}</p> : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-slate-400">Логин</label>
              <input
                required
                className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                value={cuUser}
                onChange={(e) => setCuUser(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Пароль</label>
              <input
                type="password"
                required
                minLength={6}
                className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                value={cuPass}
                onChange={(e) => setCuPass(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Имя (опционально)</label>
            <input
              className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
              value={cuName}
              onChange={(e) => setCuName(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Роль</label>
            <select
              className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
              value={cuRole}
              onChange={(e) => setCuRole(e.target.value)}
              disabled={user.role === "director"}
            >
              {user.role === "org_admin" ? (
                <>
                  <option value="director">Директор</option>
                  <option value="employee">Сотрудник</option>
                </>
              ) : (
                <option value="employee">Сотрудник</option>
              )}
            </select>
          </div>
          {(cuRole === "employee" || cuRole === "director") && (
            <fieldset className="space-y-2">
              <legend className="text-xs text-slate-400">Доступ к разделам</legend>
              <div className="flex flex-wrap gap-3">
                {SECTION_OPTIONS.map((s) => (
                  <label key={s.id} className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
                    <input
                      type="checkbox"
                      checked={cuSections.includes(s.id)}
                      onChange={(e) => setCuSections((prev) => toggleSection(prev, s.id, e.target.checked))}
                    />
                    {s.label}
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          <button
            type="submit"
            disabled={creating}
            className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            Создать
          </button>
        </form>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-slate-200">Список</h2>
        {loading ? (
          <p className="text-slate-500">Загрузка…</p>
        ) : error ? (
          <p className="text-red-400">{error}</p>
        ) : (
          <div className="space-y-6">
            {rows.map((row) => (
              <div
                key={row.id}
                className="rounded-xl border border-slate-700/80 bg-slate-900/30 p-4 text-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-mono text-sky-300">{row.username}</span>
                    <span className="ml-2 text-slate-500">· {roleLabel(row.role)}</span>
                    {misDoctorPortalIds.has(String(row.id)) ? (
                      <span className="ml-2 rounded bg-teal-900/50 px-1.5 py-0.5 text-xs text-teal-200">врач МИС</span>
                    ) : null}
                    {!row.is_active ? <span className="ml-2 text-amber-400">отключён</span> : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {isOrgAdmin &&
                    row.is_active &&
                    !misDoctorPortalIds.has(String(row.id)) &&
                    (row.role === "employee" || row.role === "director" || row.role === "org_admin") ? (
                      <button
                        type="button"
                        className="rounded border border-teal-700 px-2 py-1 text-xs text-teal-200 hover:bg-teal-950/80"
                        onClick={() => onAssignMisDoctor(row)}
                      >
                        Назначить врачом
                      </button>
                    ) : null}
                    {row.id !== user.id && (user.role === "org_admin" || (user.role === "director" && row.role === "employee")) ? (
                      <button
                        type="button"
                        className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
                        onClick={() => onToggleActive(row)}
                      >
                        {row.is_active ? "Отключить" : "Включить"}
                      </button>
                    ) : null}
                    {(user.role === "org_admin" && row.role !== "org_admin") ||
                    (user.role === "director" && row.role === "employee") ? (
                      <button
                        type="button"
                        className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
                        onClick={() => onResetPassword(row.id, row.username)}
                      >
                        Сброс пароля
                      </button>
                    ) : null}
                  </div>
                </div>
                {(row.role === "employee" || row.role === "director") &&
                  (user.role === "org_admin" || (user.role === "director" && row.role === "employee")) && (
                    <EmployeeSectionsEditor row={row} onSave={(secs) => onSaveSections(row, secs)} />
                  )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function EmployeeSectionsEditor({ row, onSave }) {
  const initial = Array.isArray(row.permissions?.sections) ? row.permissions.sections : ["qa-analytics"];
  const [local, setLocal] = useState([...initial]);

  useEffect(() => {
    setLocal(Array.isArray(row.permissions?.sections) ? [...row.permissions.sections] : ["qa-analytics"]);
  }, [row.permissions]);

  const toggle = (id, on) => {
    if (on) setLocal((p) => (p.includes(id) ? p : [...p, id]));
    else setLocal((p) => p.filter((x) => x !== id));
  };

  return (
    <div className="mt-3 border-t border-slate-800 pt-3">
      <p className="mb-2 text-xs text-slate-500">Разделы панели</p>
      <div className="flex flex-wrap gap-3">
        {SECTION_OPTIONS.map((s) => (
          <label key={s.id} className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={local.includes(s.id)}
              onChange={(e) => toggle(s.id, e.target.checked)}
            />
            {s.label}
          </label>
        ))}
      </div>
      <button
        type="button"
        className={`${BTN_SAVE_COMPACT} mt-2 text-xs`}
        onClick={() => onSave(local)}
      >
        <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
        Сохранить разделы
      </button>
    </div>
  );
}
