import { useCallback, useEffect, useState } from "react";
import { Building2 } from "lucide-react";
import { Navigate } from "react-router-dom";
import api from "../api/client.js";
import { useAuthStore } from "../store/authStore.js";

export function OrganizationsPage() {
  const user = useAuthStore((s) => s.user);

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [adminUser, setAdminUser] = useState("");
  const [adminPass, setAdminPass] = useState("");
  const [adminName, setAdminName] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get("/portal/organizations");
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e?.response?.data?.detail ?? e?.message ?? String(e));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (user?.role !== "super_admin") {
    return <Navigate to="/scenarios/qa-analytics" replace />;
  }

  const onCreate = async (e) => {
    e.preventDefault();
    setMsg("");
    setSaving(true);
    try {
      await api.post("/portal/organizations", {
        name: name.trim(),
        slug: slug.trim() || null,
        admin_username: adminUser.trim(),
        admin_password: adminPass,
        admin_display_name: adminName.trim() || null,
      });
      setName("");
      setSlug("");
      setAdminUser("");
      setAdminPass("");
      setAdminName("");
      setMsg("Организация и администратор созданы. Передайте логин и пароль представителю компании.");
      await load();
    } catch (err) {
      const d = err?.response?.data?.detail;
      setMsg(typeof d === "string" ? d : "Ошибка создания");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="w-full min-w-0 space-y-8 text-slate-100">
      <div>
        <h1 className="text-2xl font-bold text-white">Организации</h1>
        <p className="mt-2 text-sm text-slate-400">
          Создайте организацию и учётную запись <strong className="text-slate-300">администратора организации </strong>
          (логин и пароль для входа). Свободной регистрации нет.
        </p>
      </div>

      <section className="rounded-xl border border-slate-700/80 bg-slate-900/40 p-6">
        <h2 className="text-lg font-semibold text-slate-200">Новая организация</h2>
        <form className="mt-4 space-y-4" onSubmit={onCreate}>
          {msg ? (
            <p
              className={`text-sm ${msg.startsWith("Организация") ? "text-emerald-400" : "text-red-400"}`}
              role="status"
            >
              {msg}
            </p>
          ) : null}
          <div>
            <label className="mb-1 block text-xs text-slate-400" htmlFor="org-name">
              Название организации
            </label>
            <input
              id="org-name"
              required
              className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400" htmlFor="org-slug">
              Код (slug), опционально
            </label>
            <input
              id="org-slug"
              className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
              placeholder="латиница, например acme-corp"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-slate-400" htmlFor="org-admin-user">
                Логин администратора организации
              </label>
              <input
                id="org-admin-user"
                required
                autoComplete="off"
                className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                value={adminUser}
                onChange={(e) => setAdminUser(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400" htmlFor="org-admin-pass">
                Пароль администратора
              </label>
              <input
                id="org-admin-pass"
                type="password"
                required
                minLength={6}
                className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
                value={adminPass}
                onChange={(e) => setAdminPass(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400" htmlFor="org-admin-dn">
              Имя для отображения (опционально)
            </label>
            <input
              id="org-admin-dn"
              className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white"
              value={adminName}
              onChange={(e) => setAdminName(e.target.value)}
            />
          </div>
          <button
            type="submit"
            disabled={saving}
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
        ) : rows.length === 0 ? (
          <p className="text-slate-500">Пока нет организаций.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-700/80">
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-slate-600 bg-slate-900/60">
                  <th className="px-3 py-2 text-xs font-medium uppercase text-slate-400">Название</th>
                  <th className="px-3 py-2 text-xs font-medium uppercase text-slate-400">Slug</th>
                  <th className="px-3 py-2 text-xs font-medium uppercase text-slate-400">Активна</th>
                  <th className="px-3 py-2 text-xs font-medium uppercase text-slate-400">Создана</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((o) => (
                  <tr key={o.id} className="border-b border-slate-800">
                    <td className="px-3 py-2 text-slate-200">{o.name}</td>
                    <td className="px-3 py-2 font-mono text-xs text-slate-400">{o.slug}</td>
                    <td className="px-3 py-2">{o.is_active ? "да" : "нет"}</td>
                    <td className="px-3 py-2 text-slate-500">
                      {o.created_at ? new Date(o.created_at).toLocaleString("ru-RU") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
