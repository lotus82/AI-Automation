import { ArrowLeft, Building2, Loader2, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import api from "../../api/client.js";
import { useAuthStore } from "../../store/authStore.js";
import {
  BTN_SAVE,
  PAGE_H1,
  PAGE_HEADER_BETWEEN,
  PAGE_INNER,
  PAGE_SHELL,
  PAGE_TEXT,
} from "../../styles/pageLayout.js";

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

const ORG_OPTIONS = [
  { value: "OOO", label: "Общество с ограниченной ответственностью (ООО)" },
  { value: "AO", label: "Акционерное общество (АО)" },
  { value: "IP", label: "Индивидуальный предприниматель (ИП)" },
  { value: "NKO", label: "НКО / некоммерческая организация" },
];

const TAX_OPTIONS = [
  { value: "OSNO", label: "ОСНО" },
  { value: "USN_INCOME", label: "УСН (доходы)" },
  { value: "USN_INCOME_EXPENSE", label: "УСН (доходы минус расходы)" },
  { value: "PATENT", label: "Патент (ПСН)" },
];

const inputBase =
  "w-full rounded-lg border border-slate-600 bg-slate-950/80 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-600/60";

/** Текстовые поля карточки устава (произвольный JSON сохраняем вместе с ними). */
const CHARTER_TEXT_KEYS = ["charter_excerpts", "устав_text", "excerpts"];

function extractCharterText(rules) {
  if (!rules || typeof rules !== "object") return "";
  for (const k of CHARTER_TEXT_KEYS) {
    const v = rules[k];
    if (typeof v === "string" && v.trim()) return v;
  }
  return "";
}

export function LegalProfilePage() {
  const user = useAuthStore((s) => s.user);
  const role = user?.role;
  const canAccess = role === "super_admin" || role === "org_admin" || role === "director";

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");

  const [orgType, setOrgType] = useState("OOO");
  const [taxSystem, setTaxSystem] = useState("OSNO");
  const [generalDirectorName, setGeneralDirectorName] = useState("");
  const [charterText, setCharterText] = useState("");
  const [hasEmployees, setHasEmployees] = useState(true);

  /** Остальные ключи charter_rules без перезаписи текста из textarea. */
  const [rulesRest, setRulesRest] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get("/compliance/profile");
      setOrgType(data.org_type || "OOO");
      setTaxSystem(data.tax_system || "OSNO");
      setGeneralDirectorName(typeof data.general_director_name === "string" ? data.general_director_name : "");
      const cr = data.charter_rules && typeof data.charter_rules === "object" ? data.charter_rules : {};
      setCharterText(extractCharterText(cr));
      if (typeof cr.has_employees === "boolean") {
        setHasEmployees(cr.has_employees);
      } else {
        setHasEmployees(true);
      }
      const rest = { ...cr };
      CHARTER_TEXT_KEYS.forEach((k) => {
        delete rest[k];
      });
      delete rest.has_employees;
      setRulesRest(rest);
    } catch (e) {
      if (e?.response?.status === 404) {
        setOrgType("OOO");
        setTaxSystem("USN_INCOME");
        setGeneralDirectorName("");
        setCharterText("");
        setHasEmployees(false);
        setRulesRest({});
        setBanner("Профиль ещё не создан — заполните форму и сохраните.");
      } else {
        setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (canAccess) load();
  }, [canAccess, load]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    setBanner("");
    const charter_rules = {
      ...rulesRest,
      charter_excerpts: charterText,
      has_employees: hasEmployees,
    };
    try {
      await api.put("/compliance/profile", {
        org_type: orgType,
        tax_system: taxSystem,
        general_director_name: generalDirectorName.trim(),
        charter_rules,
      });
      setBanner("Профиль сохранён.");
      await load();
    } catch (err) {
      setError(formatApiDetail(err?.response?.data?.detail) || err?.message || String(err));
    } finally {
      setSaving(false);
    }
  };

  if (!user) return null;
  if (!canAccess) return <Navigate to="/scenarios/qa-analytics" replace />;

  return (
    <div className={`${PAGE_SHELL} ${PAGE_INNER} space-y-6 px-4 py-6 sm:px-6`}>
      <div className={PAGE_HEADER_BETWEEN}>
        <div className="flex items-center gap-3">
          <Link
            to="/compliance"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-600 px-2 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden />
            Комплаенс
          </Link>
          <h1 className={`${PAGE_H1} ${PAGE_TEXT} flex items-center gap-2`}>
            <Building2 className="h-7 w-7 text-emerald-400" strokeWidth={1.75} aria-hidden />
            Профиль организации (комплаенс)
          </h1>
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-200">{error}</div>
      ) : null}
      {banner ? (
        <div className="rounded-lg border border-emerald-800 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-200">
          {banner}
        </div>
      ) : null}

      {loading ? (
        <div className="flex items-center gap-2 text-slate-400">
          <Loader2 className="h-6 w-6 animate-spin" aria-hidden />
          Загрузка профиля…
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="max-w-2xl space-y-6 rounded-xl border border-slate-700 bg-slate-900/50 p-6">
          <div className="space-y-1">
            <label className="text-sm font-medium text-slate-300" htmlFor="org-type">
              Организационно-правовая форма
            </label>
            <select id="org-type" className={inputBase} value={orgType} onChange={(e) => setOrgType(e.target.value)}>
              {ORG_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium text-slate-300" htmlFor="tax-system">
              Система налогообложения
            </label>
            <select
              id="tax-system"
              className={inputBase}
              value={taxSystem}
              onChange={(e) => setTaxSystem(e.target.value)}
            >
              {TAX_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium text-slate-300" htmlFor="director-name">
              ФИО генерального директора (или ответственного лица)
            </label>
            <input
              id="director-name"
              type="text"
              maxLength={512}
              value={generalDirectorName}
              onChange={(e) => setGeneralDirectorName(e.target.value)}
              className={inputBase}
              placeholder='Например: Иванов Иван Иванович'
            />
          </div>

          <fieldset className="flex items-center gap-2 rounded-lg border border-slate-700/80 px-3 py-2">
            <input
              id="has-employees"
              type="checkbox"
              checked={hasEmployees}
              onChange={(e) => setHasEmployees(e.target.checked)}
              className="h-4 w-4 rounded border-slate-500 bg-slate-950 text-emerald-600 focus:ring-emerald-600"
            />
            <label htmlFor="has-employees" className="text-sm text-slate-300">
              В организации есть сотрудники (для напоминаний по отчётности, в т.ч. РСВ)
            </label>
          </fieldset>

          <div className="space-y-1">
            <label htmlFor="charter-excerpts" className="text-sm font-medium text-slate-300">
              Выдержки из Устава (кворумы, порядок созыва, ограничения полномочий)
            </label>
            <p className="text-xs text-slate-500">
              Эти формулировки подставляет ИИ-юрист при генерации протоколов. Пользуйтесь текстом вашего утверждённого
              устава или краткой выжимкой.
            </p>
            <textarea
              id="charter-excerpts"
              value={charterText}
              onChange={(e) => setCharterText(e.target.value)}
              rows={12}
              className={`${inputBase} font-mono text-xs leading-relaxed`}
              spellCheck={false}
              placeholder="Статья Х. Кворум для принятия решений по вопросам ...&#10;Решение по вопросу ... принимается большинством не менее 2/3 голосов..."
            />
          </div>

          <div className="pt-2">
            <button type="submit" disabled={saving} className={BTN_SAVE}>
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  Сохранение…
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" aria-hidden />
                  Сохранить профиль
                </>
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
