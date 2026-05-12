import {
  AlertCircle,
  CalendarClock,
  Download,
  Eye,
  FileDown,
  FileText,
  Loader2,
  Plus,
  RefreshCcw,
  Save,
  Settings,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import api from "../../api/client.js";
import { SK } from "../../constants/systemSettingsKeys.js";
import { useAuthStore } from "../../store/authStore.js";
import { PAGE_HEADER_BETWEEN, PAGE_H1, PAGE_INNER, PAGE_SHELL, PAGE_TEXT } from "../../styles/pageLayout.js";
import { formatDateRu, parseToLocalDate } from "../../utils/dateTimeFormat.js";
import { mapFromList } from "../../utils/systemSettingsForm.js";

function formatApiDetail(d) {
  if (d == null) return "";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d
      .map((item) => (typeof item === "string" ? item : item?.msg ? String(item.msg) : JSON.stringify(item)))
      .filter(Boolean)
      .join("; ");
  }
  if (typeof d === "object") return d.message ? String(d.message) : JSON.stringify(d);
  return String(d);
}

function daysUntilDue(isoDate) {
  const d = parseToLocalDate(isoDate);
  if (!d) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const t = d.getTime() - today.getTime();
  return Math.round(t / (24 * 60 * 60 * 1000));
}

function deadlineRowClass(dueDate, status) {
  const days = daysUntilDue(dueDate);
  if (status === "overdue" || (days != null && days < 0)) {
    return "border-l-4 border-l-red-500 bg-red-950/30";
  }
  if (days != null && days >= 0 && days < 7) {
    return "border-l-4 border-l-amber-400 bg-amber-950/25";
  }
  return "border-l-4 border-l-transparent";
}

function normId(x) {
  return String(x ?? "").trim();
}

/** Опции { value, label } из JSON **SYSTEM_ROLES_CONFIG** (как на RolesPage). */
function roleSelectOptionsFromSettingsRows(rows) {
  const map = mapFromList(Array.isArray(rows) ? rows : []);
  const raw = map[SK.SYSTEM_ROLES_CONFIG]?.value;
  if (raw == null || !String(raw).trim()) return [];
  try {
    const o = JSON.parse(String(raw));
    if (!o?.roles || !Array.isArray(o.roles)) return [];
    return o.roles
      .map((r) => {
        const value = String(r?.id ?? "").trim();
        const label = String(r?.name ?? "").trim() || value || "";
        return value ? { value, label } : null;
      })
      .filter(Boolean);
  } catch {
    return [];
  }
}

export function ComplianceDashboardPage() {
  const user = useAuthStore((s) => s.user);
  const role = user?.role;
  const canAccess = role === "super_admin" || role === "org_admin" || role === "director";

  const [deadlines, setDeadlines] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [viewDoc, setViewDoc] = useState(null);
  const [viewLoading, setViewLoading] = useState(false);

  const [legalRoleOptions, setLegalRoleOptions] = useState([]);
  const [knowledgeItems, setKnowledgeItems] = useState([]);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [profileSnapshot, setProfileSnapshot] = useState(null);
  const [profileLoadError, setProfileLoadError] = useState("");
  const [systemRoleId, setSystemRoleId] = useState("");
  const [knowledgeSelected, setKnowledgeSelected] = useState(() => new Set());
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [dlRes, docRes] = await Promise.all([
        api.get("/compliance/deadlines"),
        api.get("/compliance/documents"),
      ]);
      setDeadlines(Array.isArray(dlRes.data) ? dlRes.data : []);
      setDocuments(Array.isArray(docRes.data) ? docRes.data : []);
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
      setDeadlines([]);
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadSettingsBlock = useCallback(async () => {
    setOptionsLoading(true);
    setProfileLoadError("");
    try {
      const [settingsRes, knRes, profRes] = await Promise.all([
        api.get("/settings"),
        api.get("/knowledge/items"),
        api.get("/compliance/profile").catch((e) => {
          if (e?.response?.status === 404) return { data: null };
          throw e;
        }),
      ]);
      setLegalRoleOptions(roleSelectOptionsFromSettingsRows(settingsRes.data));
      setKnowledgeItems(Array.isArray(knRes.data) ? knRes.data : []);

      const prof = profRes?.data ?? null;
      setProfileSnapshot(prof);
      if (prof) {
        setSystemRoleId(prof.system_role_id ? String(prof.system_role_id) : "");
        const raw = prof.knowledge_item_ids;
        const ids = Array.isArray(raw) ? raw.map((x) => normId(x)).filter(Boolean) : [];
        setKnowledgeSelected(new Set(ids));
      } else {
        setSystemRoleId("");
        setKnowledgeSelected(new Set());
        setProfileLoadError("Профиль комплаенса ещё не создан — при сохранении будут подставлены значения по умолчанию.");
      }
    } catch (e) {
      setLegalRoleOptions([]);
      setKnowledgeItems([]);
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    } finally {
      setOptionsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!canAccess) return;
    load();
    loadSettingsBlock();
  }, [canAccess, load, loadSettingsBlock]);

  const openView = async (id) => {
    setViewLoading(true);
    setViewDoc(null);
    try {
      const { data } = await api.get(`/compliance/documents/${id}`);
      setViewDoc(data);
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    } finally {
      setViewLoading(false);
    }
  };

  const downloadDoc = async (row) => {
    try {
      const { data } = await api.get(`/compliance/documents/${row.id}`);
      const text = data?.content ?? "";
      const safeTitle = (data?.title || row.title || "document").replace(/[/\\?%*:|"<>]/g, "-");
      const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${safeTitle}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    }
  };

  /** DOCX через axios: Bearer из интерцептора; `window.location` не передаёт JWT. */
  const downloadDocx = async (docId, titleHint) => {
    try {
      const { data } = await api.get(`/compliance/documents/${docId}/docx`, {
        responseType: "blob",
      });
      const blob = data instanceof Blob ? data : new Blob([data], { type: data.type });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const base = (titleHint || "document").replace(/[/\\?%*:|"<>]/g, "-").slice(0, 120);
      a.download = `${base || "document"}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    }
  };

  const toggleKnowledge = (id) => {
    const sid = normId(id);
    setKnowledgeSelected((prev) => {
      const next = new Set(prev);
      if (next.has(sid)) next.delete(sid);
      else next.add(sid);
      return next;
    });
  };

  const saveComplianceSettings = async () => {
    setSavingSettings(true);
    setSettingsMessage("");
    setError("");
    try {
      const org_type = profileSnapshot?.org_type ?? "OOO";
      const tax_system = profileSnapshot?.tax_system ?? "USN_INCOME";
      const general_director_name = profileSnapshot?.general_director_name ?? "";
      const charter_rules =
        profileSnapshot?.charter_rules && typeof profileSnapshot.charter_rules === "object"
          ? profileSnapshot.charter_rules
          : {};
      const body = {
        org_type,
        tax_system,
        general_director_name,
        charter_rules,
        system_role_id: systemRoleId.trim() || null,
        knowledge_item_ids: Array.from(knowledgeSelected),
      };
      const { data } = await api.put("/compliance/profile", body);
      setProfileSnapshot(data);
      setSettingsMessage("Настройки сохранены.");
      if (data?.system_role_id) setSystemRoleId(String(data.system_role_id));
      else setSystemRoleId("");
      const raw = data?.knowledge_item_ids;
      const ids = Array.isArray(raw) ? raw.map((x) => normId(x)).filter(Boolean) : [];
      setKnowledgeSelected(new Set(ids));
      setProfileLoadError("");
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    } finally {
      setSavingSettings(false);
    }
  };

  const selectedKnowledgeLabels = useMemo(() => {
    const map = new Map(knowledgeItems.map((k) => [normId(k.id), k.title]));
    return Array.from(knowledgeSelected)
      .map((id) => ({ id, title: map.get(id) || id }))
      .filter((x) => x.id);
  }, [knowledgeItems, knowledgeSelected]);

  if (!user) return null;
  if (!canAccess) return <Navigate to="/scenarios/qa-analytics" replace />;

  const upcoming = [...deadlines].sort((a, b) => String(a.due_date).localeCompare(String(b.due_date))).slice(0, 12);

  return (
    <div className={`${PAGE_SHELL} ${PAGE_INNER} space-y-8 px-4 py-6 sm:px-6`}>
      <div className={PAGE_HEADER_BETWEEN}>
        <h1 className={`${PAGE_H1} ${PAGE_TEXT} flex items-center gap-2`}>
          <CalendarClock className="h-7 w-7 text-emerald-400" strokeWidth={1.75} aria-hidden />
          Комплаенс
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/compliance/profile"
            className="rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800"
          >
            Профиль организации
          </Link>
          <Link
            to="/compliance/generate"
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            <Plus className="h-4 w-4" aria-hidden />
            Создать документ
          </Link>
          <button
            type="button"
            onClick={() => {
              load();
              loadSettingsBlock();
            }}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
          >
            <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden />
            Обновить
          </button>
        </div>
      </div>

      {error ? (
        <div className="flex items-start gap-2 rounded-lg border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-200">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>{error}</span>
        </div>
      ) : null}

      <section className="rounded-xl border border-slate-700 bg-slate-900/50 p-4 shadow-lg sm:p-6">
        <h2 className={`mb-4 flex items-center gap-2 text-lg font-semibold ${PAGE_TEXT}`}>
          <Settings className="h-5 w-5 text-slate-400" aria-hidden />
          Настройки
        </h2>
        {optionsLoading ? (
          <div className="flex items-center gap-2 text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
            Загрузка ролей и базы знаний…
          </div>
        ) : (
          <div className="space-y-5">
            {profileLoadError ? <p className="text-sm text-amber-200/90">{profileLoadError}</p> : null}
            {settingsMessage ? (
              <p className="text-sm text-emerald-400">{settingsMessage}</p>
            ) : null}

            <div className="space-y-1">
              <label htmlFor="compliance-ai-role" className="block text-sm font-medium text-slate-300">
                Роль ИИ-юриста
              </label>
              <p className="text-xs text-slate-500">
                Роли из раздела «Роли» панели (**SYSTEM_ROLES_CONFIG**): для юриста используется поле промпта выбранной роли.
              </p>
              <select
                id="compliance-ai-role"
                className="w-full max-w-xl rounded-lg border border-slate-600 bg-slate-950/80 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-600/60"
                value={systemRoleId}
                onChange={(e) => setSystemRoleId(e.target.value)}
              >
                <option value="">— не выбрано (роль из общих настроек) —</option>
                {legalRoleOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <span className="block text-sm font-medium text-slate-300">Документы базы знаний</span>
              <p className="text-xs text-slate-500">
                Отметьте материалы (устав, протоколы), которые ИИ должен учитывать при генерации.
              </p>
              {knowledgeItems.length === 0 ? (
                <p className="text-sm text-slate-500">В базе знаний нет элементов для этой организации.</p>
              ) : (
                <ul className="max-h-52 space-y-2 overflow-y-auto rounded-lg border border-slate-700 bg-slate-950/40 p-3">
                  {knowledgeItems.map((k) => {
                    const sid = normId(k.id);
                    const checked = knowledgeSelected.has(sid);
                    return (
                      <li key={sid} className="flex items-start gap-2 text-sm">
                        <input
                          type="checkbox"
                          id={`kb-${sid}`}
                          checked={checked}
                          onChange={() => toggleKnowledge(sid)}
                          className="mt-1 h-4 w-4 shrink-0 rounded border-slate-500 bg-slate-900 text-emerald-600 focus:ring-emerald-600"
                        />
                        <label htmlFor={`kb-${sid}`} className="cursor-pointer text-slate-200">
                          <span className="font-medium">{k.title}</span>
                          {k.content_preview ? (
                            <span className="mt-0.5 block text-xs text-slate-500">{k.content_preview}</span>
                          ) : null}
                        </label>
                      </li>
                    );
                  })}
                </ul>
              )}
              {selectedKnowledgeLabels.length > 0 ? (
                <div className="text-xs text-slate-400">
                  Выбрано:{" "}
                  {selectedKnowledgeLabels.map((x) => (
                    <span key={x.id} className="mr-2 inline-block rounded bg-slate-800 px-2 py-0.5 text-slate-300">
                      {x.title}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>

            <button
              type="button"
              onClick={saveComplianceSettings}
              disabled={savingSettings}
              className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
            >
              {savingSettings ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <Save className="h-4 w-4" aria-hidden />
              )}
              Сохранить настройки
            </button>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-slate-700 bg-slate-900/50 p-4 shadow-lg sm:p-6">
        <h2 className={`mb-4 text-lg font-semibold ${PAGE_TEXT}`}>Ближайшие дедлайны</h2>
        {loading ? (
          <div className="flex items-center gap-2 text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
            Загрузка…
          </div>
        ) : upcoming.length === 0 ? (
          <p className="text-slate-400">Нет запланированных сроков. Проверьте профиль организации и автогенерацию в Celery.</p>
        ) : (
          <ul className="space-y-2">
            {upcoming.map((d) => {
              const days = daysUntilDue(d.due_date);
              const badge =
                d.status === "overdue" || (days != null && days < 0)
                  ? "text-red-300"
                  : days != null && days >= 0 && days < 7
                    ? "text-amber-300"
                    : "text-slate-400";
              return (
                <li
                  key={d.id}
                  className={`rounded-lg border border-slate-700/80 px-3 py-2.5 ${deadlineRowClass(d.due_date, d.status)}`}
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className={`font-medium ${PAGE_TEXT}`}>{d.title}</span>
                    <span className="text-sm text-slate-400">{formatDateRu(d.due_date)}</span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-slate-300">{d.status}</span>
                    <span className={badge}>
                      {days == null
                        ? ""
                        : days < 0
                          ? `Просрочено на ${Math.abs(days)} дн.`
                          : days === 0
                            ? "Сегодня"
                            : `Осталось ${days} дн.`}
                    </span>
                  </div>
                  {d.description ? <p className="mt-1 text-sm text-slate-500">{d.description}</p> : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="rounded-xl border border-slate-700 bg-slate-900/50 p-4 shadow-lg sm:p-6">
        <h2 className={`mb-4 text-lg font-semibold ${PAGE_TEXT} flex items-center gap-2`}>
          <FileText className="h-5 w-5 text-slate-400" aria-hidden />
          Архив документов
        </h2>
        {loading ? (
          <div className="flex items-center gap-2 text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
            Загрузка…
          </div>
        ) : documents.length === 0 ? (
          <p className="text-slate-400">Документов пока нет. Создайте первый через мастера генерации.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm text-slate-200">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400">
                  <th className="py-2 pr-4 font-medium">Название</th>
                  <th className="py-2 pr-4 font-medium">Тип</th>
                  <th className="py-2 pr-4 font-medium">Статус</th>
                  <th className="py-2 pr-4 font-medium">Обновлён</th>
                  <th className="py-2 font-medium text-right">Действия</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((row) => (
                  <tr key={row.id} className="border-b border-slate-800 hover:bg-slate-800/40">
                    <td className="py-2 pr-4 font-medium">{row.title}</td>
                    <td className="py-2 pr-4 capitalize text-slate-400">{row.doc_type}</td>
                    <td className="py-2 pr-4 text-slate-400">{row.status}</td>
                    <td className="py-2 pr-4 text-slate-500">{formatDateRu(row.updated_at)}</td>
                    <td className="py-2 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => downloadDoc(row)}
                        className="mr-2 inline-flex items-center gap-1 rounded border border-slate-600 px-2 py-1 text-xs hover:bg-slate-800"
                      >
                        <Download className="h-3.5 w-3.5" aria-hidden />
                        Скачать
                      </button>
                      <button
                        type="button"
                        onClick={() => downloadDocx(row.id, row.title)}
                        className="mr-2 inline-flex items-center gap-1 rounded border border-violet-700/50 bg-violet-950/30 px-2 py-1 text-xs text-violet-200 hover:bg-violet-900/40"
                        title="Скачать в Word"
                      >
                        <FileDown className="h-3.5 w-3.5" aria-hidden />
                        DOCX
                      </button>
                      <button
                        type="button"
                        onClick={() => openView(row.id)}
                        className="inline-flex items-center gap-1 rounded border border-emerald-700/60 bg-emerald-950/30 px-2 py-1 text-xs text-emerald-200 hover:bg-emerald-900/40"
                      >
                        <Eye className="h-3.5 w-3.5" aria-hidden />
                        Просмотр
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {viewDoc || viewLoading ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Просмотр документа"
        >
          <button
            type="button"
            tabIndex={-1}
            className="absolute inset-0 cursor-default bg-transparent"
            aria-label="Закрыть просмотр по фону"
            onClick={() => {
              setViewDoc(null);
              setViewLoading(false);
            }}
          />
          <div className="relative z-10 flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-slate-600 bg-slate-900 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-700 px-4 py-3">
              <h3 className="font-semibold text-white">{viewDoc?.title || "Загрузка…"}</h3>
              <button
                type="button"
                className="rounded-lg px-2 py-1 text-slate-400 hover:bg-slate-800 hover:text-white"
                onClick={() => {
                  setViewDoc(null);
                  setViewLoading(false);
                }}
              >
                Закрыть
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4 text-slate-200 [&_h1]:text-xl [&_h2]:text-lg [&_p]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_a]:text-emerald-400">
              {viewLoading ? (
                <div className="flex items-center gap-2 text-slate-400">
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Загрузка…
                </div>
              ) : (
                <ReactMarkdown>{viewDoc?.content || ""}</ReactMarkdown>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
