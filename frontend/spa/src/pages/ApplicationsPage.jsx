import { Check, Globe, LayoutGrid, Link as LinkIcon, RefreshCcw, Save } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import QRCode from "react-qr-code";
import api from "../api/client.js";
import {
  IconCopyButton,
  IconQrButton,
} from "../components/ui/IconActionButtons.jsx";
import { useAuthStore } from "../store/authStore.js";
import { PAGE_SHELL, PAGE_TEXT } from "../styles/pageLayout.js";
import { formatDateTimeRu } from "../utils/dateTimeFormat.js";

/** FastAPI detail → строка. */
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

/**
 * Раздел «Приложения» корпоративной панели.
 *
 * - Отображает публичную ссылку Mini App организации: `https://<host>/inn/<inn>`.
 *   Адрес берётся из профиля пользователя (`organization_inn` в /auth/me).
 * - Показывает таблицу зарегистрированных пользователей Mini App.
 */
export function ApplicationsPage() {
  const user = useAuthStore((s) => s.user);
  const settingsOrgId = useAuthStore((s) => s.settingsOrganizationId);

  const role = user?.role;
  const canAccess = role === "super_admin" || role === "org_admin" || role === "director";

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copiedLink, setCopiedLink] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);

  const [sites, setSites] = useState([]);
  const [sitesLoading, setSitesLoading] = useState(false);
  const [activeSiteId, setActiveSiteId] = useState("");
  const [savedActiveSiteId, setSavedActiveSiteId] = useState("");
  const [savingActiveSite, setSavingActiveSite] = useState(false);
  const [activeSiteJustSaved, setActiveSiteJustSaved] = useState(false);
  const [activeSiteError, setActiveSiteError] = useState("");

  const orgInn = useMemo(() => {
    const raw = (user?.organization_inn || "").trim();
    return raw || null;
  }, [user?.organization_inn]);

  const miniAppUrl = useMemo(() => {
    if (!orgInn) return null;
    const origin = typeof window !== "undefined" ? window.location.origin : "https://lotus-it.ru";
    return `${origin.replace(/\/$/, "")}/inn/${encodeURIComponent(orgInn)}`;
  }, [orgInn]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (role === "super_admin" && settingsOrgId) {
        params.organization_id = settingsOrgId;
      }
      const { data } = await api.get("/portal/miniapp/users", { params });
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [role, settingsOrgId]);

  const loadSitesAndActive = useCallback(async () => {
    setSitesLoading(true);
    setActiveSiteError("");
    try {
      const params = {};
      if (role === "super_admin" && settingsOrgId) {
        params.organization_id = settingsOrgId;
      }
      const [sitesResp, activeResp] = await Promise.all([
        api.get("/sites", { params }),
        api.get("/portal/miniapp/active-site", { params }),
      ]);
      const list = Array.isArray(sitesResp.data) ? sitesResp.data : [];
      setSites(list);
      const currentId = activeResp?.data?.active_site_id || "";
      setActiveSiteId(currentId);
      setSavedActiveSiteId(currentId);
    } catch (e) {
      setActiveSiteError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
      setSites([]);
    } finally {
      setSitesLoading(false);
    }
  }, [role, settingsOrgId]);

  useEffect(() => {
    if (canAccess) {
      load();
      loadSitesAndActive();
    }
  }, [canAccess, load, loadSitesAndActive]);

  if (!user) return null;
  if (!canAccess) return <Navigate to="/scenarios/qa-analytics" replace />;

  const saveActiveSite = async () => {
    setSavingActiveSite(true);
    setActiveSiteError("");
    setActiveSiteJustSaved(false);
    try {
      const params = {};
      if (role === "super_admin" && settingsOrgId) {
        params.organization_id = settingsOrgId;
      }
      const { data } = await api.put(
        "/portal/miniapp/active-site",
        { site_id: activeSiteId || null },
        { params },
      );
      const newId = data?.active_site_id || "";
      setSavedActiveSiteId(newId);
      setActiveSiteId(newId);
      setActiveSiteJustSaved(true);
      setTimeout(() => setActiveSiteJustSaved(false), 1500);
    } catch (e) {
      setActiveSiteError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    } finally {
      setSavingActiveSite(false);
    }
  };

  const activeSiteDirty = (activeSiteId || "") !== (savedActiveSiteId || "");

  const copyLink = async () => {
    if (!miniAppUrl) return;
    try {
      await navigator.clipboard.writeText(miniAppUrl);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 1500);
    } catch {
      // ignore — в проде можно добавить toast
    }
  };

  return (
    <div className={`${PAGE_SHELL} ${PAGE_TEXT} px-4 py-6 sm:px-6`}>
      <header className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600/20 text-emerald-300">
          <LayoutGrid className="h-5 w-5" strokeWidth={1.75} aria-hidden />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-white">Приложения</h1>
          
        </div>
      </header>

      <section className="mb-6 rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <div className="text-xs uppercase tracking-wide text-slate-500">
          Ваша ссылка для Mini App
        </div>
        {miniAppUrl ? (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <LinkIcon className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
            <a
              href={miniAppUrl}
              target="_blank"
              rel="noreferrer"
              className="min-w-0 flex-1 truncate font-mono text-sm text-emerald-300 hover:underline"
            >
              {miniAppUrl}
            </a>
            <IconCopyButton
              title="Копировать ссылку"
              copied={copiedLink}
              onClick={copyLink}
            />
            <IconQrButton title="QR-код" onClick={() => setQrOpen(true)} />
          </div>
        ) : (
          <div className="mt-2 rounded-lg border border-amber-600/40 bg-amber-500/10 p-3 text-sm text-amber-200">
            У вашей организации не указан ИНН. Попросите супер-админа добавить ИНН в карточку
            организации (раздел «Организации»), после чего здесь появится публичная ссылка на Mini App.
          </div>
        )}
        <p className="mt-2 text-xs text-slate-500">
          Передайте эту ссылку в бота MAX (кнопка Web App). При первом открытии пользователь появится
          в таблице ниже.
        </p>
      </section>

      <section className="mb-6 rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <header className="mb-3 flex items-center gap-2">
          <Globe className="h-4 w-4 text-sky-300" aria-hidden />
          <h2 className="text-sm font-semibold text-white">Настройка Mini App</h2>
        </header>
        <p className="text-xs text-slate-400">
          Выберите сайт, контент которого будет отображаться клиентам в Mini App мессенджера MAX.
          Можно менять в любой момент — клиенты увидят изменения при следующем открытии. Сайты с меткой{" "}
          <span className="text-violet-300">[МИС]</span> созданы в разделе «МИС» — те же страницы и модули,
          плюс сценарии врач/пациент по chat_id.
        </p>

        {activeSiteError ? (
          <div className="mt-3 rounded-lg border border-red-600/40 bg-red-600/10 p-3 text-sm text-red-200">
            {activeSiteError}
          </div>
        ) : null}

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <label className="flex min-w-[260px] flex-1 flex-col gap-1 text-xs font-medium text-slate-300">
            Активный сайт
            <select
              value={activeSiteId || ""}
              onChange={(e) => setActiveSiteId(e.target.value)}
              disabled={sitesLoading || savingActiveSite}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none disabled:opacity-60"
            >
              <option value="">
                {sitesLoading ? "Загрузка списка сайтов…" : "— сайт не выбран —"}
              </option>
              {sites.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.site_kind === "mis" ? " [МИС]" : ""}
                  {s.title ? ` — ${s.title}` : ""}
                </option>
              ))}
            </select>
          </label>

          <div className="flex items-end gap-2 pb-[1px]">
            <button
              type="button"
              onClick={saveActiveSite}
              disabled={!activeSiteDirty || savingActiveSite}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
            >
              {activeSiteJustSaved ? (
                <>
                  <Check className="h-3.5 w-3.5" aria-hidden />
                  Сохранено
                </>
              ) : (
                <>
                  <Save className="h-3.5 w-3.5" aria-hidden />
                  {savingActiveSite ? "Сохранение…" : "Сохранить"}
                </>
              )}
            </button>
            <button
              type="button"
              onClick={loadSitesAndActive}
              disabled={sitesLoading || savingActiveSite}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-60"
              title="Обновить список сайтов"
            >
              <RefreshCcw className={`h-3.5 w-3.5 ${sitesLoading ? "animate-spin" : ""}`} aria-hidden />
              Обновить
            </button>
          </div>
        </div>

        {sites.length === 0 && !sitesLoading ? (
          <p className="mt-3 text-xs text-slate-500">
            У организации ещё нет сайтов. Создайте сайт в разделе «Сайты» или МИС-сайт в разделе «МИС» — он
            появится в списке.
          </p>
        ) : null}
      </section>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/70">
        <header className="flex items-center justify-between gap-2 border-b border-slate-800 px-4 py-3">
          <div>
            <div className="text-sm font-semibold text-white">Пользователи Mini App</div>
            <div className="text-xs text-slate-500">
              Создаются автоматически при первом входе в Mini App.
            </div>
          </div>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-60"
          >
            <RefreshCcw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} aria-hidden />
            Обновить
          </button>
        </header>

        {error ? (
          <div className="m-3 rounded-lg border border-red-600/40 bg-red-600/10 p-3 text-sm text-red-200">
            {error}
          </div>
        ) : null}

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-800 text-sm">
            <thead className="bg-slate-900/60 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left font-medium">ID чата</th>
                <th className="px-4 py-2 text-left font-medium">Имя</th>
                <th className="px-4 py-2 text-left font-medium">Дата регистрации</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td className="px-4 py-4 text-slate-400" colSpan={3}>
                    Загрузка…
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-center text-slate-500" colSpan={3}>
                    Пока никто не открывал Mini App организации.
                  </td>
                </tr>
              ) : (
                rows.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-800/40">
                    <td className="px-4 py-2 font-mono text-slate-100">{u.chat_id}</td>
                    <td className="px-4 py-2 text-slate-200">{u.name || <span className="text-slate-500">—</span>}</td>
                    <td className="px-4 py-2 text-slate-400">{formatDateTimeRu(u.created_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {qrOpen && miniAppUrl ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm"
          role="presentation"
          onClick={() => setQrOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="miniapp-qr-title"
            className="relative w-full max-w-sm rounded-2xl border border-slate-700 bg-white p-6 text-slate-800 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="miniapp-qr-title" className="text-base font-semibold text-slate-900">
              QR: ссылка на Mini App
            </h2>
            <p className="mt-1 text-xs text-slate-600">
              Отсканируйте или передайте ссылку в настройки бота MAX.
            </p>
            <div className="mt-4 flex justify-center rounded-xl bg-white p-3 ring-1 ring-slate-100">
              <QRCode value={miniAppUrl} size={220} level="M" />
            </div>
            <p className="mt-4 break-all font-mono text-[11px] leading-snug text-slate-700">
              {miniAppUrl}
            </p>
            <button
              type="button"
              onClick={() => setQrOpen(false)}
              className="mt-4 w-full rounded-lg border border-slate-300 bg-slate-100 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200"
            >
              Закрыть
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
