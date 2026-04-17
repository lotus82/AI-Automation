import {
  ArrowLeft,
  ArrowDownWideNarrow,
  Eye,
  EyeOff,
  FileText,
  Palette,
  Plus,
  RefreshCcw,
  Save,
  Settings as SettingsIcon,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import api from "../../api/client.js";
import { useAuthStore } from "../../store/authStore.js";
import { PAGE_SHELL, PAGE_TEXT, TAB_ROW, tabBtn } from "../../styles/pageLayout.js";
import { formatDateTimeRu } from "../../utils/dateTimeFormat.js";

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

/** Пустые контакты — используется для начального состояния формы. */
const EMPTY_CONTACTS = {
  phone: "",
  email: "",
  address: "",
  website: "",
  telegram: "",
  vk: "",
  max: "",
  whatsapp: "",
  instagram: "",
};

/** Поля, которые можно показывать в UI контактов. */
const CONTACT_FIELDS = [
  { key: "phone", label: "Телефон", placeholder: "+7 999 000-00-00", type: "tel" },
  { key: "email", label: "Email", placeholder: "hello@example.com", type: "email" },
  { key: "address", label: "Адрес", placeholder: "г. Саратов, ул. Ленина, 1", type: "text" },
  { key: "website", label: "Сайт", placeholder: "https://lotus-it.ru", type: "url" },
  { key: "telegram", label: "Telegram", placeholder: "@username", type: "text" },
  { key: "vk", label: "VK", placeholder: "https://vk.com/…", type: "text" },
  { key: "max", label: "MAX", placeholder: "https://max.ru/…", type: "text" },
  { key: "whatsapp", label: "WhatsApp", placeholder: "+7 999 000-00-00", type: "text" },
  { key: "instagram", label: "Instagram", placeholder: "@handle", type: "text" },
];

/**
 * Конструктор сайта: настройки / список страниц / редактор страницы.
 * Роут: /sites/:id
 */
export function SiteBuilderPage() {
  const navigate = useNavigate();
  const { id: siteId } = useParams();
  const user = useAuthStore((s) => s.user);
  const role = user?.role;
  const canAccess = role === "super_admin" || role === "org_admin" || role === "director";

  const [tab, setTab] = useState("settings"); // settings | pages | page-editor
  const [site, setSite] = useState(null);
  const [loadingSite, setLoadingSite] = useState(true);
  const [error, setError] = useState("");

  // Форма настроек
  const [form, setForm] = useState({
    name: "",
    title: "",
    subtitle: "",
    logo_url: "",
    theme_color: "#000000",
    contacts: EMPTY_CONTACTS,
  });
  const [savingSite, setSavingSite] = useState(false);
  const [savedAt, setSavedAt] = useState(null);

  // Страницы
  const [pages, setPages] = useState([]);
  const [loadingPages, setLoadingPages] = useState(false);
  const [editingPageId, setEditingPageId] = useState(null);
  const [pageForm, setPageForm] = useState({
    title: "",
    slug: "",
    content: "",
    order_index: 0,
    is_published: true,
  });
  const [pageSaving, setPageSaving] = useState(false);

  const editingPage = useMemo(
    () => pages.find((p) => p.id === editingPageId) || null,
    [pages, editingPageId],
  );

  const loadSite = useCallback(async () => {
    if (!siteId) return;
    setLoadingSite(true);
    setError("");
    try {
      const { data } = await api.get(`/sites/${siteId}`);
      setSite(data);
      setForm({
        name: data.name || "",
        title: data.title || "",
        subtitle: data.subtitle || "",
        logo_url: data.logo_url || "",
        theme_color: data.theme_color || "#000000",
        contacts: { ...EMPTY_CONTACTS, ...(data.contacts || {}) },
      });
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
      setSite(null);
    } finally {
      setLoadingSite(false);
    }
  }, [siteId]);

  const loadPages = useCallback(async () => {
    if (!siteId) return;
    setLoadingPages(true);
    try {
      const { data } = await api.get(`/sites/${siteId}/pages`);
      setPages(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
      setPages([]);
    } finally {
      setLoadingPages(false);
    }
  }, [siteId]);

  useEffect(() => {
    if (canAccess) {
      loadSite();
      loadPages();
    }
  }, [canAccess, loadSite, loadPages]);

  if (!user) return null;
  if (!canAccess) return <Navigate to="/scenarios/qa-analytics" replace />;

  // --- Настройки сайта -----------------------------------------------

  const setContactField = (key, value) => {
    setForm((prev) => ({ ...prev, contacts: { ...prev.contacts, [key]: value } }));
  };

  const onSaveSite = async (e) => {
    e?.preventDefault();
    if (!siteId) return;
    setSavingSite(true);
    setError("");
    try {
      // contacts: убираем пустые значения, чтобы не хранить пустые строки в JSONB
      const cleanContacts = Object.fromEntries(
        Object.entries(form.contacts || {})
          .map(([k, v]) => [k, typeof v === "string" ? v.trim() : v])
          .filter(([, v]) => v !== "" && v != null),
      );
      const payload = {
        name: form.name.trim(),
        title: form.title.trim(),
        subtitle: form.subtitle.trim(),
        logo_url: form.logo_url.trim(),
        theme_color: form.theme_color || "#000000",
        contacts: cleanContacts,
      };
      const { data } = await api.put(`/sites/${siteId}`, payload);
      setSite(data);
      setSavedAt(new Date());
    } catch (err) {
      setError(formatApiDetail(err?.response?.data?.detail) || err?.message || String(err));
    } finally {
      setSavingSite(false);
    }
  };

  // --- Страницы: порядок, создание, удаление, редактирование ----------

  const onChangePageOrder = async (pageId, nextOrder) => {
    const prev = pages;
    const next = prev.map((p) => (p.id === pageId ? { ...p, order_index: nextOrder } : p));
    next.sort((a, b) => a.order_index - b.order_index);
    setPages(next);
    try {
      await api.put(`/sites/${siteId}/pages/${pageId}`, { order_index: nextOrder });
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
      setPages(prev);
    }
  };

  const onTogglePublished = async (pageId, nextVal) => {
    const prev = pages;
    setPages(prev.map((p) => (p.id === pageId ? { ...p, is_published: nextVal } : p)));
    try {
      await api.put(`/sites/${siteId}/pages/${pageId}`, { is_published: nextVal });
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
      setPages(prev);
    }
  };

  const onCreatePage = async () => {
    const base = { title: "Новая страница", slug: `page-${Date.now().toString(36)}`, content: "" };
    try {
      const nextOrder =
        (pages.reduce((acc, p) => Math.max(acc, p.order_index || 0), -1) || 0) + 1;
      const { data } = await api.post(`/sites/${siteId}/pages`, {
        ...base,
        order_index: nextOrder,
        is_published: true,
      });
      setPages((prev) => [...prev, data].sort((a, b) => a.order_index - b.order_index));
      openPageEditor(data);
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    }
  };

  const onDeletePage = async (pageId, title) => {
    if (!window.confirm(`Удалить страницу «${title}»?`)) return;
    try {
      await api.delete(`/sites/${siteId}/pages/${pageId}`);
      setPages((prev) => prev.filter((p) => p.id !== pageId));
      if (editingPageId === pageId) {
        setEditingPageId(null);
        setTab("pages");
      }
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
    }
  };

  const openPageEditor = (p) => {
    setEditingPageId(p.id);
    setPageForm({
      title: p.title || "",
      slug: p.slug || "",
      content: p.content || "",
      order_index: p.order_index ?? 0,
      is_published: Boolean(p.is_published),
    });
    setTab("page-editor");
  };

  const onSavePage = async (e) => {
    e?.preventDefault();
    if (!editingPageId) return;
    setPageSaving(true);
    setError("");
    try {
      const payload = {
        title: pageForm.title.trim(),
        slug: (pageForm.slug || "").trim().toLowerCase(),
        content: pageForm.content,
        order_index: Math.max(0, Number(pageForm.order_index) || 0),
        is_published: Boolean(pageForm.is_published),
      };
      const { data } = await api.put(`/sites/${siteId}/pages/${editingPageId}`, payload);
      setPages((prev) =>
        prev
          .map((p) => (p.id === data.id ? data : p))
          .sort((a, b) => a.order_index - b.order_index),
      );
      setSavedAt(new Date());
    } catch (err) {
      setError(formatApiDetail(err?.response?.data?.detail) || err?.message || String(err));
    } finally {
      setPageSaving(false);
    }
  };

  // --- Render ---------------------------------------------------------

  return (
    <div className={`${PAGE_SHELL} ${PAGE_TEXT} px-4 py-6 sm:px-6`}>
      <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate("/sites")}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
            title="К списку сайтов"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            Сайты
          </button>
          <div>
            <h1 className="text-xl font-semibold text-white">
              {loadingSite ? "Загрузка…" : site?.name || "Сайт"}
            </h1>
            <p className="text-sm text-slate-400">Конструктор содержимого Mini App.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              loadSite();
              loadPages();
            }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
          >
            <RefreshCcw className="h-3.5 w-3.5" aria-hidden />
            Обновить
          </button>
          {savedAt ? (
            <span className="text-xs text-emerald-300">Сохранено {formatDateTimeRu(savedAt.toISOString())}</span>
          ) : null}
        </div>
      </header>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-600/40 bg-red-600/10 p-3 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      <div className={TAB_ROW} role="tablist">
        <button type="button" className={tabBtn(tab === "settings")} onClick={() => setTab("settings")}>
          <span className="inline-flex items-center gap-1.5">
            <SettingsIcon className="h-3.5 w-3.5" aria-hidden />
            Настройки
          </span>
        </button>
        <button type="button" className={tabBtn(tab === "pages")} onClick={() => setTab("pages")}>
          <span className="inline-flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5" aria-hidden />
            Страницы
          </span>
        </button>
        <button
          type="button"
          className={tabBtn(tab === "page-editor")}
          onClick={() => (editingPageId ? setTab("page-editor") : null)}
          disabled={!editingPageId}
          title={editingPageId ? "Редактор страницы" : "Выберите страницу во вкладке «Страницы»"}
        >
          <span className="inline-flex items-center gap-1.5">
            <Palette className="h-3.5 w-3.5" aria-hidden />
            Редактор страницы
          </span>
        </button>
      </div>

      <div className="rounded-b-2xl rounded-tr-2xl border border-t-0 border-slate-600 bg-slate-900/60 p-4 sm:p-6">
        {tab === "settings" ? (
          <SettingsTab
            form={form}
            setForm={setForm}
            setContactField={setContactField}
            onSave={onSaveSite}
            saving={savingSite}
            loading={loadingSite}
          />
        ) : null}

        {tab === "pages" ? (
          <PagesTab
            pages={pages}
            loading={loadingPages}
            onCreate={onCreatePage}
            onOpen={openPageEditor}
            onDelete={onDeletePage}
            onChangeOrder={onChangePageOrder}
            onTogglePublished={onTogglePublished}
          />
        ) : null}

        {tab === "page-editor" ? (
          <PageEditorTab
            page={editingPage}
            form={pageForm}
            setForm={setPageForm}
            onSave={onSavePage}
            saving={pageSaving}
            onDelete={() =>
              editingPage ? onDeletePage(editingPage.id, editingPage.title) : null
            }
            onBackToList={() => setTab("pages")}
          />
        ) : null}
      </div>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <label className="block text-xs font-medium text-slate-300">
      {label}
      {children}
      {hint ? <span className="mt-1 block text-[11px] font-normal text-slate-500">{hint}</span> : null}
    </label>
  );
}

const inputClass =
  "mt-1 block w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-emerald-500 focus:outline-none";

function SettingsTab({ form, setForm, setContactField, onSave, saving, loading }) {
  if (loading) return <div className="py-6 text-center text-slate-400">Загрузка…</div>;
  return (
    <form onSubmit={onSave} className="grid gap-6 lg:grid-cols-2">
      <section className="space-y-4">
        <h2 className="text-sm font-semibold text-white">Общие</h2>
        <Field label="Внутреннее название" hint="Видно только в админ-панели.">
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            className={inputClass}
            required
            maxLength={255}
          />
        </Field>
        <Field label="Главный заголовок (для клиентов)">
          <input
            type="text"
            value={form.title}
            onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
            className={inputClass}
            maxLength={255}
            placeholder="Например: Клиника LotusMed"
          />
        </Field>
        <Field label="Краткое описание">
          <textarea
            value={form.subtitle}
            onChange={(e) => setForm((p) => ({ ...p, subtitle: e.target.value }))}
            className={`${inputClass} min-h-[72px] resize-y`}
            maxLength={512}
            placeholder="Что предлагает сайт, 1–2 предложения"
          />
        </Field>
        <Field label="URL логотипа" hint="Можно указать полную ссылку на изображение.">
          <input
            type="url"
            value={form.logo_url}
            onChange={(e) => setForm((p) => ({ ...p, logo_url: e.target.value }))}
            className={inputClass}
            maxLength={1024}
            placeholder="https://…/logo.png"
          />
        </Field>
        <Field label="Цвет темы" hint="HEX-код, используется как акцент в Mini App.">
          <div className="mt-1 flex items-center gap-3">
            <input
              type="color"
              value={/^#[0-9a-fA-F]{6}$/.test(form.theme_color) ? form.theme_color : "#000000"}
              onChange={(e) => setForm((p) => ({ ...p, theme_color: e.target.value }))}
              className="h-9 w-12 cursor-pointer rounded-lg border border-slate-700 bg-slate-950"
            />
            <input
              type="text"
              value={form.theme_color}
              onChange={(e) => setForm((p) => ({ ...p, theme_color: e.target.value }))}
              className={`${inputClass} !mt-0 flex-1 font-mono`}
              maxLength={16}
              placeholder="#000000"
            />
          </div>
        </Field>
      </section>

      <section className="space-y-4">
        <h2 className="text-sm font-semibold text-white">Контакты</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {CONTACT_FIELDS.map((c) => (
            <Field key={c.key} label={c.label}>
              <input
                type={c.type}
                value={form.contacts?.[c.key] || ""}
                onChange={(e) => setContactField(c.key, e.target.value)}
                className={inputClass}
                placeholder={c.placeholder}
                maxLength={512}
              />
            </Field>
          ))}
        </div>
      </section>

      <div className="lg:col-span-2 flex justify-end">
        <button
          type="submit"
          disabled={saving}
          className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
        >
          <Save className="h-4 w-4" aria-hidden />
          {saving ? "Сохранение…" : "Сохранить настройки"}
        </button>
      </div>
    </form>
  );
}

function PagesTab({ pages, loading, onCreate, onOpen, onDelete, onChangeOrder, onTogglePublished }) {
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm text-slate-400">
          Порядок отображения задаётся полем «порядок» — меньше число, выше в меню.
        </div>
        <button
          type="button"
          onClick={onCreate}
          className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden />
          Новая страница
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="min-w-full divide-y divide-slate-800 text-sm">
          <thead className="bg-slate-900/70 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="w-20 px-3 py-2 text-left font-medium">
                <span className="inline-flex items-center gap-1">
                  <ArrowDownWideNarrow className="h-3.5 w-3.5" aria-hidden />
                  Порядок
                </span>
              </th>
              <th className="px-3 py-2 text-left font-medium">Заголовок</th>
              <th className="px-3 py-2 text-left font-medium">Slug</th>
              <th className="w-28 px-3 py-2 text-left font-medium">Статус</th>
              <th className="w-48 px-3 py-2 text-right font-medium">Действия</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {loading ? (
              <tr>
                <td className="px-3 py-4 text-slate-400" colSpan={5}>
                  Загрузка…
                </td>
              </tr>
            ) : pages.length === 0 ? (
              <tr>
                <td className="px-3 py-6 text-center text-slate-500" colSpan={5}>
                  Страниц нет. Создайте первую — это может быть «Главная», «О нас», «FAQ».
                </td>
              </tr>
            ) : (
              pages.map((p) => (
                <tr key={p.id} className="hover:bg-slate-800/40">
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      min={0}
                      max={10000}
                      value={p.order_index}
                      onChange={(e) =>
                        onChangeOrder(p.id, Math.max(0, Number(e.target.value) || 0))
                      }
                      className="w-20 rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={() => onOpen(p)}
                      className="text-left font-medium text-slate-100 hover:text-emerald-300"
                    >
                      {p.title}
                    </button>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-400">/{p.slug}</td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={() => onTogglePublished(p.id, !p.is_published)}
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                        p.is_published
                          ? "bg-emerald-600/20 text-emerald-300"
                          : "bg-slate-700/60 text-slate-300"
                      }`}
                      title={p.is_published ? "Скрыть страницу" : "Опубликовать"}
                    >
                      {p.is_published ? (
                        <>
                          <Eye className="h-3 w-3" aria-hidden /> Опубликована
                        </>
                      ) : (
                        <>
                          <EyeOff className="h-3 w-3" aria-hidden /> Черновик
                        </>
                      )}
                    </button>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        onClick={() => onOpen(p)}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800/70 px-2.5 py-1 text-xs font-medium text-slate-200 hover:bg-slate-700"
                      >
                        Редактировать
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete(p.id, p.title)}
                        className="inline-flex items-center gap-1 rounded-lg border border-red-700/60 bg-red-900/30 px-2 py-1 text-xs font-medium text-red-200 hover:bg-red-900/60"
                        title="Удалить"
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PageEditorTab({ page, form, setForm, onSave, saving, onDelete, onBackToList }) {
  if (!page) {
    return (
      <div className="py-8 text-center text-slate-400">
        Страница не выбрана. Откройте вкладку «Страницы» и выберите нужную.
      </div>
    );
  }
  return (
    <form onSubmit={onSave} className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-slate-500">
          Обновлено: {formatDateTimeRu(page.updated_at)}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onBackToList}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
          >
            К списку страниц
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="inline-flex items-center gap-1.5 rounded-lg border border-red-700/60 bg-red-900/30 px-3 py-1.5 text-xs font-medium text-red-200 hover:bg-red-900/60"
          >
            <Trash2 className="h-3.5 w-3.5" aria-hidden />
            Удалить
          </button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Заголовок">
          <input
            type="text"
            value={form.title}
            onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
            className={inputClass}
            required
            maxLength={255}
          />
        </Field>
        <Field label="Slug (часть URL)" hint="Латиница, цифры, дефис. Уникален в пределах сайта.">
          <input
            type="text"
            value={form.slug}
            onChange={(e) => setForm((p) => ({ ...p, slug: e.target.value }))}
            className={`${inputClass} font-mono`}
            required
            maxLength={128}
          />
        </Field>
        <Field label="Порядок">
          <input
            type="number"
            min={0}
            max={10000}
            value={form.order_index}
            onChange={(e) =>
              setForm((p) => ({ ...p, order_index: Math.max(0, Number(e.target.value) || 0) }))
            }
            className={inputClass}
          />
        </Field>
        <Field label="Публикация" hint="Черновики не видны в публичном Mini App.">
          <div className="mt-2">
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-slate-200">
              <input
                type="checkbox"
                checked={Boolean(form.is_published)}
                onChange={(e) => setForm((p) => ({ ...p, is_published: e.target.checked }))}
                className="h-4 w-4 rounded border-slate-600 bg-slate-950 text-emerald-500 focus:ring-emerald-500"
              />
              Опубликована
            </label>
          </div>
        </Field>
      </div>

      <Field
        label="Контент"
        hint="Пока — простой текст / HTML / Markdown. В будущем подключим WYSIWYG."
      >
        <textarea
          value={form.content}
          onChange={(e) => setForm((p) => ({ ...p, content: e.target.value }))}
          className={`${inputClass} min-h-[360px] font-mono text-[13px]`}
          maxLength={500000}
          placeholder="<h1>Добро пожаловать</h1>&#10;<p>Описание вашего сервиса…</p>"
        />
      </Field>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={saving}
          className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
        >
          <Save className="h-4 w-4" aria-hidden />
          {saving ? "Сохранение…" : "Сохранить страницу"}
        </button>
      </div>
    </form>
  );
}
