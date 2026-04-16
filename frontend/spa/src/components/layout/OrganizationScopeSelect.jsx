import { useCallback, useEffect, useState } from "react";
import api from "../../api/client.js";
import { useAuthStore } from "../../store/authStore.js";

/** Для super_admin: выбор организации для запросов к /settings и /knowledge (глобальный экземпляр или org). */
export function OrganizationScopeSelect() {
  const user = useAuthStore((s) => s.user);
  const settingsOrganizationId = useAuthStore((s) => s.settingsOrganizationId);
  const setSettingsOrganizationId = useAuthStore((s) => s.setSettingsOrganizationId);

  const [orgs, setOrgs] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/portal/organizations");
      setOrgs(Array.isArray(data) ? data : []);
    } catch {
      setOrgs([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user?.role === "super_admin") {
      void load();
    }
  }, [user?.role, load]);

  if (user?.role !== "super_admin") {
    return null;
  }

  return (
    <label className="mt-3 flex flex-col gap-1 border-t border-slate-800 pt-3 text-xs text-slate-400">
      <span className="font-medium text-slate-500">Контекст настроек и БЗ</span>
      <select
        className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-200"
        value={settingsOrganizationId ?? ""}
        disabled={loading}
        onChange={(e) => {
          const v = e.target.value;
          setSettingsOrganizationId(v ? v : null);
        }}
      >
        <option value="">Глобально (экземпляр)</option>
        {orgs.map((o) => (
          <option key={o.id} value={o.id}>
            {o.display_name || o.name || o.slug || o.id}
          </option>
        ))}
      </select>
    </label>
  );
}
