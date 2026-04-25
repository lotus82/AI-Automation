import {
  ArrowDown,
  ArrowLeft,
  ArrowDownWideNarrow,
  ArrowUp,
  Eye,
  EyeOff,
  FileText,
  LayoutGrid,
  Menu,
  Palette,
  Plus,
  QrCode,
  RefreshCcw,
  Save,
  Settings as SettingsIcon,
  Smartphone,
  Stethoscope,
  Trash2,
  Upload,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import Cropper from "react-easy-crop";
import ReactQuill from "react-quill";
import "react-easy-crop/react-easy-crop.css";
import "react-quill/dist/quill.snow.css";
import api from "../../api/client.js";
import { useMiniAppHtmlLinkDelegate } from "../../hooks/useMiniAppHtmlLinkDelegate.js";
import { MiniAppEmbedPlaceholder } from "../miniapp/MiniAppEmbedPlaceholder.jsx";
import { useAuthStore } from "../../store/authStore.js";
import {
  BTN_SAVE,
  ICON_BTN,
  PAGE_H1,
  PAGE_HEADER_BETWEEN,
  PAGE_SHELL,
  PAGE_TEXT,
  PAGE_TITLE_ICON,
  TAB_ROW,
  tabBtn,
} from "../../styles/pageLayout.js";
import { formatDateTimeRu } from "../../utils/dateTimeFormat.js";
import { siteLogoImgSrc } from "../../utils/siteLogoUrl.js";
import {
  isValidMisLogoIconKey,
  MedicalColorPresetRow,
  MisLogoIcon,
  MIS_LOGO_ICON_OPTIONS,
} from "../../utils/misMedicalBranding.jsx";
import { buildSberQrDonationBlockHtml, SBER_DONATION_DEFAULT_HREF } from "../../utils/sberDonationBlockHtml";
import {
  PATIENT_PUBLIC_SECTION_LABELS,
  normalizePublicSectionOrder,
} from "../../utils/patientPublicCardLayout.js";
import { MIS_DOCTOR_PAGE_KINDS, MIS_PATIENT_PAGE_KINDS } from "../../utils/misMiniAppNav.js";

/** Ключи встраиваемых модулей Mini App (согласовано с backend). */
const EMBED_MODULE_OPTIONS = [
  { value: "", label: "Нет встроенного модуля" },
  { value: "knowledge", label: "База знаний" },
  { value: "roles", label: "Роли и промпты" },
  { value: "questionnaires", label: "Опросники" },
  { value: "forms", label: "Формы" },
  { value: "shops", label: "Магазины" },
  { value: "integrations", label: "Интеграции" },
  { value: "schedule", label: "Расписание (сценарии)" },
  { value: "bookings", label: "Записи (список/аналитика)" },
  { value: "bots", label: "Боты и каналы" },
  { value: "logs", label: "Логи" },
  { value: "applications", label: "Приложения" },
  { value: "sites", label: "Сайты" },
  { value: "mis", label: "МИС" },
  { value: "chats", label: "Чаты" },
];

/** Область кропа в пикселях исходного изображения (как в react-easy-crop). */
function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.addEventListener("load", () => resolve(image));
    image.addEventListener("error", (err) => reject(err));
    image.src = src;
  });
}

/**
 * Вырезает прямоугольник в PNG (поддержка прозрачности у логотипов).
 * @param {string} imageSrc object URL или URL
 * @param {{ x: number, y: number, width: number, height: number }} pixelCrop
 * @returns {Promise<Blob>}
 */
async function getCroppedImgBlob(imageSrc, pixelCrop) {
  const image = await loadImage(imageSrc);
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unsupported");
  canvas.width = Math.max(1, Math.round(pixelCrop.width));
  canvas.height = Math.max(1, Math.round(pixelCrop.height));
  ctx.drawImage(
    image,
    pixelCrop.x,
    pixelCrop.y,
    pixelCrop.width,
    pixelCrop.height,
    0,
    0,
    canvas.width,
    canvas.height,
  );
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) reject(new Error("Пустое изображение после кропа"));
        else resolve(blob);
      },
      "image/png",
      1,
    );
  });
}

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

function mapMenuItemsFromApi(arr) {
  if (!Array.isArray(arr)) return [];
  return arr.map((m) => ({
    id:
      m.id ||
      (typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : String(Math.random())),
    label: m.label || "",
    page_id: m.page_id,
    order_index: m.order_index ?? 0,
    is_visible: m.is_visible !== false,
  }));
}

/** Вкладка «Карта пациента»: тема публичной карты (хранится в contacts.mis_patient_card_theme). */
function PatientCardThemePanel({ form, setForm, onSave, saving }) {
  const raw = form.contacts?.mis_patient_card_theme;
  const theme =
    raw && typeof raw === "object" && !Array.isArray(raw)
      ? raw
      : { accent_color: "#0ea5e9", card_radius: 16, header_style: "gradient" };
  const setTheme = (patch) => {
    setForm((prev) => ({
      ...prev,
      contacts: {
        ...prev.contacts,
        mis_patient_card_theme: { ...theme, ...patch },
      },
    }));
  };
  return (
    <form onSubmit={onSave} className="space-y-4">
      <p className="text-sm text-slate-400">
        Эти параметры применяются к публичной карте пациента (
        <code className="rounded bg-slate-800 px-1 text-xs">/public/mis/patient/…</code>) и передаются в Mini App
        в конфиге.
      </p>
      <label className="block text-xs font-medium text-slate-300">
        Акцентный цвет
        <input
          type="color"
          value={typeof theme.accent_color === "string" ? theme.accent_color : "#0ea5e9"}
          onChange={(e) => setTheme({ accent_color: e.target.value })}
          className="mt-1 h-10 w-full max-w-[120px] cursor-pointer rounded border border-slate-700 bg-slate-950"
        />
      </label>
      <div className="space-y-1.5">
        <div className="text-xs text-slate-500">Медицинская палитра</div>
        <MedicalColorPresetRow
          value={typeof theme.accent_color === "string" ? theme.accent_color : "#0ea5e9"}
          onChange={(hex) => setTheme({ accent_color: hex })}
        />
      </div>
      <label className="block text-xs font-medium text-slate-300">
        Скругление карточек (px)
        <input
          type="number"
          min={0}
          max={48}
          value={Number(theme.card_radius) || 16}
          onChange={(e) => setTheme({ card_radius: Math.min(48, Math.max(0, Number(e.target.value) || 0)) })}
          className="mt-1 block w-full max-w-[200px] rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
        />
      </label>
      <label className="block text-xs font-medium text-slate-300">
        Шапка карты
        <select
          value={theme.header_style === "solid" ? "solid" : "gradient"}
          onChange={(e) => setTheme({ header_style: e.target.value })}
          className="mt-1 block w-full max-w-[280px] rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
        >
          <option value="gradient">Градиент (акцентный цвет)</option>
          <option value="solid">Сплошная заливка</option>
        </select>
      </label>

      <div className="rounded-lg border border-slate-600 bg-slate-950/50 p-3">
        <div className="text-xs font-medium text-slate-200">Порядок блоков на публичной карте</div>
        <p className="mt-1 text-[11px] leading-snug text-slate-500">
          Пациент видит разделы в этом порядке. Те же секции использует карта в Mini App (после входа по chat_id).
        </p>
        <ul className="mt-3 space-y-1.5">
          {normalizePublicSectionOrder(theme).map((key, idx, arr) => (
            <li
              key={key}
              className="flex items-center gap-2 rounded-md border border-slate-700/80 bg-slate-900/60 px-2 py-1.5 text-xs text-slate-200"
            >
              <span className="min-w-0 flex-1">
                {idx + 1}. {PATIENT_PUBLIC_SECTION_LABELS[key] || key}
              </span>
              <button
                type="button"
                title="Выше"
                disabled={idx === 0}
                onClick={() => {
                  if (idx === 0) return;
                  const next = [...arr];
                  [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
                  setTheme({ public_section_order: next });
                }}
                className="rounded border border-slate-600 p-1 text-slate-300 hover:bg-slate-800 disabled:opacity-30"
              >
                <ArrowUp className="h-3.5 w-3.5" aria-hidden />
              </button>
              <button
                type="button"
                title="Ниже"
                disabled={idx >= arr.length - 1}
                onClick={() => {
                  if (idx >= arr.length - 1) return;
                  const next = [...arr];
                  [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
                  setTheme({ public_section_order: next });
                }}
                className="rounded border border-slate-600 p-1 text-slate-300 hover:bg-slate-800 disabled:opacity-30"
              >
                <ArrowDown className="h-3.5 w-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-lg border border-slate-600 bg-slate-950/40 p-3">
        <div className="text-xs font-medium text-slate-200">Как видит врач (упрощённо)</div>
        <p className="mt-1 text-[11px] text-slate-500">
          Превью порядка блоков: у врача в панели МИС отдельный экран карты; у пациента — публичная страница с теми же
          разделами ниже.
        </p>
        <div
          className="mt-3 space-y-2 rounded-xl border border-slate-700/80 bg-white p-3 text-slate-800"
          style={{
            borderRadius: Math.min(48, Math.max(0, Number(theme.card_radius) || 16)),
          }}
        >
          <div
            className="-mx-3 -mt-3 mb-2 px-3 py-2 text-[11px] font-medium text-white"
            style={{
              borderTopLeftRadius: Math.min(48, Math.max(0, Number(theme.card_radius) || 16)),
              borderTopRightRadius: Math.min(48, Math.max(0, Number(theme.card_radius) || 16)),
              background:
                theme.header_style === "solid"
                  ? typeof theme.accent_color === "string"
                    ? theme.accent_color
                    : "#0ea5e9"
                  : `linear-gradient(135deg, ${typeof theme.accent_color === "string" ? theme.accent_color : "#0ea5e9"} 0%, ${typeof theme.accent_color === "string" ? theme.accent_color : "#0ea5e9"}dd 100%)`,
            }}
          >
            Карта пациента
          </div>
          {normalizePublicSectionOrder(theme).map((key) => (
            <div
              key={key}
              className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-[11px] font-medium text-slate-700"
            >
              {PATIENT_PUBLIC_SECTION_LABELS[key] || key}
            </div>
          ))}
        </div>
      </div>

      <button type="submit" disabled={saving} className={BTN_SAVE}>
        <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
        {saving ? "Сохранение…" : "Сохранить тему"}
      </button>
    </form>
  );
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
  payment_url: "",
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
  const location = useLocation();
  const { id: siteId } = useParams();
  const isMisBuilder = location.pathname.startsWith("/mis/sites");
  const user = useAuthStore((s) => s.user);
  const role = user?.role;
  const canAccess = role === "super_admin" || role === "org_admin" || role === "director";

  const [tab, setTab] = useState("settings"); // settings | menu | pages | page-editor
  /** Для МИС: какую роль редактируем (отдельные страницы и меню). */
  const [misRoleTab, setMisRoleTab] = useState("doctor");
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
    menu_items: [],
    mis_menu_items_doctor: [],
    mis_menu_items_patient: [],
  });
  const [savingSite, setSavingSite] = useState(false);
  const [savingMenu, setSavingMenu] = useState(false);
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
    page_kind: "content",
    booking_staff_user_id: "",
    embed_module: "",
    linked_document_id: "",
    mis_audience: "doctor",
  });
  const [pageSaving, setPageSaving] = useState(false);
  const [portalUsers, setPortalUsers] = useState([]);
  const [documentsList, setDocumentsList] = useState([]);

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
        contacts: {
          ...EMPTY_CONTACTS,
          ...(data.contacts || {}),
          mis_miniapp_audience:
            (data.contacts || {}).mis_miniapp_audience === "patient" ? "patient" : "doctor",
        },
        menu_items: mapMenuItemsFromApi(data.menu_items),
        mis_menu_items_doctor: mapMenuItemsFromApi(data.mis_menu_items_doctor),
        mis_menu_items_patient: mapMenuItemsFromApi(data.mis_menu_items_patient),
      });
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
      setSite(null);
    } finally {
      setLoadingSite(false);
    }
  }, [siteId]);

  const loadDocumentsForPicker = useCallback(async () => {
    if (!canAccess) return;
    try {
      const { data } = await api.get("/documents");
      setDocumentsList(Array.isArray(data) ? data : []);
    } catch {
      setDocumentsList([]);
    }
  }, [canAccess]);

  useEffect(() => {
    loadDocumentsForPicker();
  }, [loadDocumentsForPicker]);

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

  const loadPortalUsers = useCallback(async () => {
    if (!site?.organization_id) {
      setPortalUsers([]);
      return;
    }
    try {
      const params = {};
      if (user?.role === "super_admin") {
        params.organization_id = site.organization_id;
      }
      const { data } = await api.get("/portal/users", { params });
      setPortalUsers(Array.isArray(data) ? data : []);
    } catch {
      setPortalUsers([]);
    }
  }, [site?.organization_id, user?.role]);

  useEffect(() => {
    if (canAccess) {
      loadSite();
      loadPages();
    }
  }, [canAccess, loadSite, loadPages]);

  useEffect(() => {
    if (canAccess && site?.organization_id && tab === "page-editor") {
      loadPortalUsers();
    }
  }, [canAccess, site?.organization_id, tab, loadPortalUsers]);

  if (!user) return null;
  if (!canAccess) return <Navigate to="/scenarios/qa-analytics" replace />;

  const isMisSite = isMisBuilder || (site?.site_kind || "") === "mis";

  const pagesForMisRole = (() => {
    if (!isMisSite) return pages;
    const aud = misRoleTab === "doctor" ? "doctor" : "patient";
    return pages.filter((p) => {
      const ma = String(p.mis_audience || "").toLowerCase();
      if (!ma) return true;
      return ma === aud;
    });
  })();

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
      if (Array.isArray(data.menu_items)) {
        setForm((prev) => ({
          ...prev,
          menu_items: mapMenuItemsFromApi(data.menu_items),
          mis_menu_items_doctor: mapMenuItemsFromApi(data.mis_menu_items_doctor),
          mis_menu_items_patient: mapMenuItemsFromApi(data.mis_menu_items_patient),
        }));
      }
      setSavedAt(new Date());
    } catch (err) {
      setError(formatApiDetail(err?.response?.data?.detail) || err?.message || String(err));
    } finally {
      setSavingSite(false);
    }
  };

  const onSaveMenu = async (e) => {
    e?.preventDefault();
    if (!siteId) return;
    setSavingMenu(true);
    setError("");
    try {
      const payload = isMisSite
        ? {
            mis_menu_items_doctor: (form.mis_menu_items_doctor || []).map((it, idx) => ({
              id: it.id,
              label: (it.label || "").trim() || "Пункт",
              page_id: it.page_id,
              order_index: Math.max(0, Number(it.order_index) || idx),
              is_visible: Boolean(it.is_visible),
            })),
            mis_menu_items_patient: (form.mis_menu_items_patient || []).map((it, idx) => ({
              id: it.id,
              label: (it.label || "").trim() || "Пункт",
              page_id: it.page_id,
              order_index: Math.max(0, Number(it.order_index) || idx),
              is_visible: Boolean(it.is_visible),
            })),
          }
        : {
            menu_items: (form.menu_items || []).map((it, idx) => ({
              id: it.id,
              label: (it.label || "").trim() || "Пункт",
              page_id: it.page_id,
              order_index: Math.max(0, Number(it.order_index) || idx),
              is_visible: Boolean(it.is_visible),
            })),
          };
      const { data } = await api.put(`/sites/${siteId}`, payload);
      setSite(data);
      setForm((prev) => ({
        ...prev,
        menu_items: mapMenuItemsFromApi(data.menu_items),
        mis_menu_items_doctor: mapMenuItemsFromApi(data.mis_menu_items_doctor),
        mis_menu_items_patient: mapMenuItemsFromApi(data.mis_menu_items_patient),
      }));
      setSavedAt(new Date());
    } catch (err) {
      setError(formatApiDetail(err?.response?.data?.detail) || err?.message || String(err));
    } finally {
      setSavingMenu(false);
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
      const scope = isMisSite ? pagesForMisRole : pages;
      const nextOrder =
        (scope.reduce((acc, p) => Math.max(acc, p.order_index || 0), -1) || 0) + 1;
      const { data } = await api.post(`/sites/${siteId}/pages`, {
        ...base,
        order_index: nextOrder,
        is_published: true,
        ...(isMisSite
          ? {
              page_kind: coerceMisPageKindForAudience("mis_patients", misRoleTab === "patient"),
            }
          : {}),
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
    if (isMisSite) {
      const ma = String(p.mis_audience || "").toLowerCase();
      if (ma === "patient") setMisRoleTab("patient");
      else if (ma === "doctor") setMisRoleTab("doctor");
    }
    const audiencePatient = isMisSite
      ? (() => {
          const ma = String(p.mis_audience || "").toLowerCase();
          if (ma === "patient") return true;
          if (ma === "doctor") return false;
          return misRoleTab === "patient";
        })()
      : form?.contacts?.mis_miniapp_audience === "patient";
    const pageKind = isMisSite
      ? coerceMisPageKindForAudience(p.page_kind, audiencePatient)
      : normalizeSitePageKind(p.page_kind);
    setPageForm({
      title: p.title || "",
      slug: p.slug || "",
      content: p.content || "",
      order_index: p.order_index ?? 0,
      is_published: Boolean(p.is_published),
      page_kind: pageKind,
      booking_staff_user_id: p.booking_staff_user_id ? String(p.booking_staff_user_id) : "",
      embed_module: p.embed_module ? String(p.embed_module) : "",
      linked_document_id: p.linked_document_id ? String(p.linked_document_id) : "",
      mis_audience: String(p.mis_audience || "").toLowerCase() === "patient" ? "patient" : "doctor",
    });
    setTab("page-editor");
  };

  const onSavePage = async (e) => {
    e?.preventDefault();
    if (!editingPageId) return;
    setPageSaving(true);
    setError("");
    try {
      const pk = normalizeSitePageKind(pageForm.page_kind);
      const staffRaw = (pageForm.booking_staff_user_id || "").trim();
      const docRaw = (pageForm.linked_document_id || "").trim();
      const payload = {
        title: pageForm.title.trim(),
        slug: (pageForm.slug || "").trim().toLowerCase(),
        content: pageForm.content,
        order_index: Math.max(0, Number(pageForm.order_index) || 0),
        is_published: Boolean(pageForm.is_published),
        page_kind: pk,
        booking_staff_user_id:
          pk === "booking" && staffRaw ? staffRaw : null,
        embed_module:
          pk === "content" && (pageForm.embed_module || "").trim()
            ? String(pageForm.embed_module).trim()
            : null,
        linked_document_id: pk === "document_reader" && docRaw ? docRaw : null,
      };
      if (isMisSite && pk === "document_reader") {
        payload.mis_audience = pageForm.mis_audience === "patient" ? "patient" : "doctor";
      }
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
      <header className={PAGE_HEADER_BETWEEN}>
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => navigate(isMisBuilder ? "/mis" : "/sites")}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
            title={isMisBuilder ? "К списку МИС-сайтов" : "К списку сайтов"}
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            {isMisBuilder ? "МИС" : "Сайты"}
          </button>
          {isMisBuilder ? (
            <Stethoscope className={PAGE_TITLE_ICON} strokeWidth={1.5} aria-hidden />
          ) : (
            <LayoutGrid className={PAGE_TITLE_ICON} strokeWidth={1.5} aria-hidden />
          )}
          <div className="min-w-0">
            <h1 className={PAGE_H1}>
              {loadingSite ? "Загрузка…" : site?.name || "Сайт"}
            </h1>
            <p className="text-sm text-slate-400">
              {isMisSite
                ? "Конструктор МИС-сайта (Mini App): меню, страницы, тема публичной карты пациента."
                : "Конструктор содержимого Mini App."}
            </p>
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
        {isMisSite ? (
          <button
            type="button"
            className={tabBtn(tab === "patient-card")}
            onClick={() => setTab("patient-card")}
          >
            <span className="inline-flex items-center gap-1.5">
              <Stethoscope className="h-3.5 w-3.5" aria-hidden />
              Карта пациента
            </span>
          </button>
        ) : null}
        <button type="button" className={tabBtn(tab === "menu")} onClick={() => setTab("menu")}>
          <span className="inline-flex items-center gap-1.5">
            <Menu className="h-3.5 w-3.5" aria-hidden />
            Меню
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
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="min-w-0">
            {tab === "settings" ? (
              <SettingsTab
                siteId={siteId}
                form={form}
                setForm={setForm}
                setSite={setSite}
                setContactField={setContactField}
                setError={setError}
                onSave={onSaveSite}
                saving={savingSite}
                loading={loadingSite}
                isMisSite={isMisSite}
              />
            ) : null}

            {tab === "patient-card" && isMisSite ? (
              <PatientCardThemePanel form={form} setForm={setForm} onSave={onSaveSite} saving={savingSite} />
            ) : null}

            {tab === "menu" ? (
              <MenuTab
                form={form}
                setForm={setForm}
                pages={pages}
                pagesForPicker={isMisSite ? pagesForMisRole : pages}
                loading={loadingSite || loadingPages}
                onSave={onSaveMenu}
                saving={savingMenu}
                isMisSite={isMisSite}
                misRoleTab={misRoleTab}
                setMisRoleTab={setMisRoleTab}
              />
            ) : null}

            {tab === "pages" ? (
              <PagesTab
                pages={isMisSite ? pagesForMisRole : pages}
                loading={loadingPages}
                onCreate={onCreatePage}
                onOpen={openPageEditor}
                onDelete={onDeletePage}
                onChangeOrder={onChangePageOrder}
                onTogglePublished={onTogglePublished}
                isMisSite={isMisSite}
                misRoleTab={misRoleTab}
                setMisRoleTab={setMisRoleTab}
              />
            ) : null}

            {tab === "page-editor" ? (
              <PageEditorTab
                page={editingPage}
                form={pageForm}
                setForm={setPageForm}
                portalUsers={portalUsers}
                documentsList={documentsList}
                paymentLinkDefault={(form.contacts?.payment_url || "").trim()}
                onSave={onSavePage}
                saving={pageSaving}
                isMisSite={isMisSite}
                misAudiencePatient={isMisSite ? misRoleTab === "patient" : form.contacts?.mis_miniapp_audience === "patient"}
                onDelete={() =>
                  editingPage ? onDeletePage(editingPage.id, editingPage.title) : null
                }
                onBackToList={() => setTab("pages")}
              />
            ) : null}
          </div>

          <aside className="min-w-0">
            <div className="xl:sticky xl:top-4">
              <MiniAppPreview
                tab={tab}
                form={form}
                pages={pages}
                editingPageId={editingPageId}
                pageForm={pageForm}
                isMisSite={isMisSite}
                misRoleTab={misRoleTab}
                setMisRoleTab={setMisRoleTab}
              />
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

/**
 * Редактор нижнего меню Mini App: подпись пункта, порядок, привязка к странице, видимость.
 */
function MenuTab({
  form,
  setForm,
  pages,
  pagesForPicker,
  loading,
  onSave,
  saving,
  isMisSite = false,
  misRoleTab = "doctor",
  setMisRoleTab,
}) {
  const pickerPages = pagesForPicker ?? pages;
  const menuKey = isMisSite
    ? misRoleTab === "doctor"
      ? "mis_menu_items_doctor"
      : "mis_menu_items_patient"
    : "menu_items";

  if (loading) return <div className="py-6 text-center text-slate-400">Загрузка…</div>;

  const fillFromPages = () => {
    const pub = [...pickerPages]
      .filter((p) => p.is_published)
      .sort((a, b) => (a.order_index || 0) - (b.order_index || 0));
    setForm((prev) => ({
      ...prev,
      [menuKey]: pub.map((p, i) => ({
        id:
          typeof crypto !== "undefined" && crypto.randomUUID
            ? crypto.randomUUID()
            : `m-${i}-${Date.now()}`,
        label: p.title || "",
        page_id: p.id,
        order_index: i,
        is_visible: true,
      })),
    }));
  };

  const addRow = () => {
    const pub = pickerPages.filter((p) => p.is_published);
    const first = pub[0] || pickerPages[0];
    if (!first) return;
    setForm((prev) => ({
      ...prev,
      [menuKey]: [
        ...(prev[menuKey] || []),
        {
          id:
            typeof crypto !== "undefined" && crypto.randomUUID
              ? crypto.randomUUID()
              : `m-${Date.now()}`,
          label: "Новый пункт",
          page_id: first.id,
          order_index: (prev[menuKey] || []).length,
          is_visible: true,
        },
      ],
    }));
  };

  const removeRow = (id) => {
    setForm((prev) => ({
      ...prev,
      [menuKey]: (prev[menuKey] || []).filter((x) => x.id !== id),
    }));
  };

  const updateRow = (id, patch) => {
    setForm((prev) => ({
      ...prev,
      [menuKey]: (prev[menuKey] || []).map((x) => (x.id === id ? { ...x, ...patch } : x)),
    }));
  };

  const rows = [...(form[menuKey] || [])].sort(
    (a, b) => (Number(a.order_index) || 0) - (Number(b.order_index) || 0),
  );

  return (
    <form onSubmit={onSave} className="space-y-4">
      <p className="text-sm text-slate-400">
        Пункты нижнего меню в Mini App: своя подпись, порядок и страница. Если меню пустое и так
        сохранено — подписи и порядок совпадают с опубликованными страницами.
      </p>
      {isMisSite ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/50 px-3 py-2">
          <span className="text-xs font-medium text-slate-400">Роль в Mini App:</span>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setMisRoleTab?.("doctor")}
              className={`rounded-md px-3 py-1 text-xs font-medium ${
                misRoleTab === "doctor"
                  ? "bg-emerald-600 text-white"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              Врач
            </button>
            <button
              type="button"
              onClick={() => setMisRoleTab?.("patient")}
              className={`rounded-md px-3 py-1 text-xs font-medium ${
                misRoleTab === "patient"
                  ? "bg-emerald-600 text-white"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              Пациент
            </button>
          </div>
          <span className="text-[11px] text-slate-500">
            У каждой роли своё меню; сохранение отправляет оба набора на сервер.
          </span>
        </div>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={fillFromPages}
          disabled={!pickerPages.some((p) => p.is_published)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-50"
        >
          Заполнить из страниц
        </button>
        <button
          type="button"
          onClick={addRow}
          disabled={pickerPages.length === 0}
          className="inline-flex items-center gap-1.5 rounded-lg bg-slate-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-600 disabled:opacity-50"
        >
          <Plus className={ICON_BTN} strokeWidth={2} aria-hidden />
          Добавить пункт
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="min-w-full divide-y divide-slate-800 text-sm">
          <thead className="bg-slate-900/70 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="w-20 px-3 py-2 text-left font-medium">Порядок</th>
              <th className="px-3 py-2 text-left font-medium">Подпись в меню</th>
              <th className="min-w-[180px] px-3 py-2 text-left font-medium">Страница</th>
              <th className="w-28 px-3 py-2 text-left font-medium">В меню</th>
              <th className="w-14 px-3 py-2 text-right font-medium" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {rows.length === 0 ? (
              <tr>
                <td className="px-3 py-6 text-center text-slate-500" colSpan={5}>
                  Пунктов нет — в Mini App будет автоматическое меню из опубликованных страниц.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.id} className="hover:bg-slate-800/40">
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      min={0}
                      max={100000}
                      value={row.order_index}
                      onChange={(e) =>
                        updateRow(row.id, { order_index: Math.max(0, Number(e.target.value) || 0) })
                      }
                      className="w-20 rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={row.label}
                      onChange={(e) => updateRow(row.id, { label: e.target.value })}
                      className="w-full min-w-[140px] rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
                      maxLength={128}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <select
                      value={row.page_id != null ? String(row.page_id) : ""}
                      onChange={(e) => updateRow(row.id, { page_id: e.target.value })}
                      className="w-full min-w-[160px] rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
                    >
                      {pickerPages.map((p) => (
                        <option key={p.id} value={String(p.id)}>
                          {p.is_published ? "" : "⚠ "}
                          {p.title} (/{p.slug})
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-2">
                    <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-slate-200">
                      <input
                        type="checkbox"
                        checked={Boolean(row.is_visible)}
                        onChange={(e) => updateRow(row.id, { is_visible: e.target.checked })}
                        className="h-4 w-4 rounded border-slate-600 bg-slate-950 text-emerald-500 focus:ring-emerald-500"
                      />
                      Да
                    </label>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => removeRow(row.id)}
                      className="inline-flex rounded-lg border border-red-700/60 bg-red-900/30 p-1.5 text-red-200 hover:bg-red-900/60"
                      title="Удалить пункт"
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex justify-end">
        <button type="submit" disabled={saving} className={BTN_SAVE}>
          <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
          {saving ? "Сохранение…" : "Сохранить меню"}
        </button>
      </div>
    </form>
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

const ALL_MIS_PAGE_KINDS = [...MIS_DOCTOR_PAGE_KINDS, ...MIS_PATIENT_PAGE_KINDS];

function normalizeSitePageKind(raw) {
  const s = String(raw || "content").toLowerCase();
  if (
    ALL_MIS_PAGE_KINDS.includes(s) ||
    s === "booking" ||
    s === "content" ||
    s === "document_reader" ||
    s === "profile"
  ) {
    return s;
  }
  return "content";
}

function coerceMisPageKindForAudience(kind, audienceIsPatient) {
  const k = normalizeSitePageKind(kind);
  if (k === "document_reader") return "document_reader";
  const doctor = new Set(MIS_DOCTOR_PAGE_KINDS);
  const patient = new Set(MIS_PATIENT_PAGE_KINDS);
  if (audienceIsPatient) {
    return patient.has(k) ? k : "mis_patient_card";
  }
  return doctor.has(k) ? k : "mis_patients";
}

function SettingsTab({
  siteId,
  form,
  setForm,
  setSite,
  setContactField,
  setError,
  onSave,
  saving,
  loading,
  isMisSite = false,
}) {
  const fileInputRef = useRef(null);
  const [cropOpen, setCropOpen] = useState(false);
  const [imageSrc, setImageSrc] = useState(null);
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState(null);
  const [logoUploading, setLogoUploading] = useState(false);

  const closeCropModal = useCallback(() => {
    if (imageSrc) {
      try {
        URL.revokeObjectURL(imageSrc);
      } catch {
        /* ignore */
      }
    }
    setImageSrc(null);
    setCropOpen(false);
    setCrop({ x: 0, y: 0 });
    setZoom(1);
    setCroppedAreaPixels(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, [imageSrc]);

  const onCropComplete = useCallback((_area, areaPixels) => {
    setCroppedAreaPixels(areaPixels);
  }, []);

  const onPickLogoFile = useCallback(
    (e) => {
      const file = e.target.files?.[0];
      if (!file || !file.type.startsWith("image/")) {
        setError("Выберите файл изображения.");
        return;
      }
      const url = URL.createObjectURL(file);
      setImageSrc(url);
      setCropOpen(true);
      setCrop({ x: 0, y: 0 });
      setZoom(1);
      setCroppedAreaPixels(null);
    },
    [setError],
  );

  const onApplyCropAndUpload = useCallback(async () => {
    if (!siteId || !imageSrc || !croppedAreaPixels) return;
    setLogoUploading(true);
    setError("");
    try {
      const blob = await getCroppedImgBlob(imageSrc, croppedAreaPixels);
      const fd = new FormData();
      fd.append("file", blob, "logo.png");
      const { data } = await api.post(`/sites/${siteId}/logo`, fd);
      setForm((p) => ({ ...p, logo_url: data.logo_url || "" }));
      setSite(data);
      closeCropModal();
    } catch (err) {
      setError(formatApiDetail(err?.response?.data?.detail) || err?.message || String(err));
    } finally {
      setLogoUploading(false);
    }
  }, [siteId, imageSrc, croppedAreaPixels, setForm, setSite, setError, closeCropModal]);

  if (loading) return <div className="py-6 text-center text-slate-400">Загрузка…</div>;
  return (
    <form onSubmit={onSave} className="grid gap-6 lg:grid-cols-2">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        className="hidden"
        onChange={onPickLogoFile}
      />

      {cropOpen && imageSrc ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="logo-crop-title"
        >
          <div className="flex max-h-[90vh] w-full max-w-lg flex-col rounded-2xl border border-slate-600 bg-slate-900 shadow-xl">
            <h3 id="logo-crop-title" className="border-b border-slate-700 px-4 py-3 text-sm font-semibold text-white">
              Область логотипа
            </h3>
            <p className="px-4 pt-3 text-xs text-slate-400">
              Перетащите и масштабируйте изображение; рамка задаёт зону кропа.
            </p>
            <div className="relative mx-4 mt-3 h-64 w-auto overflow-hidden rounded-lg bg-slate-950 md:h-72">
              <Cropper
                image={imageSrc}
                crop={crop}
                zoom={zoom}
                onCropChange={setCrop}
                onZoomChange={setZoom}
                onCropComplete={onCropComplete}
              />
            </div>
            <div className="px-4 py-3">
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <span className="shrink-0">Масштаб</span>
                <input
                  type="range"
                  min={1}
                  max={3}
                  step={0.05}
                  value={zoom}
                  onChange={(e) => setZoom(Number(e.target.value))}
                  className="min-w-0 flex-1"
                />
              </label>
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-700 px-4 py-3">
              <button
                type="button"
                onClick={closeCropModal}
                className="rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800"
              >
                Отмена
              </button>
              <button
                type="button"
                disabled={logoUploading || !croppedAreaPixels}
                onClick={onApplyCropAndUpload}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
              >
                <Upload className="h-4 w-4" aria-hidden />
                {logoUploading ? "Загрузка…" : "Обрезать и загрузить"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <section className="space-y-4">
        <h2 className="text-sm font-semibold text-white">Общие</h2>
        {isMisSite ? (
          <div className="rounded-lg border border-slate-700 bg-slate-950/40 px-3 py-2 text-xs text-slate-400">
            Страницы и нижнее меню настраиваются{' '}
            <strong className="text-slate-300">отдельно для врача и для пациента</strong> на вкладках «Страницы» и
            «Меню» (переключатель роли). В Mini App пользователь видит только свой набор.
          </div>
        ) : null}
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
        <Field
          label="URL логотипа"
          hint="Полная ссылка или путь вида /api/public/sites/assets/… после загрузки файла."
        >
          <div className="mt-1 flex flex-col gap-2 sm:flex-row sm:items-stretch">
            <input
              type="text"
              value={form.logo_url}
              onChange={(e) => setForm((p) => ({ ...p, logo_url: e.target.value }))}
              className={`${inputClass} !mt-0 sm:min-w-0 sm:flex-1`}
              maxLength={1024}
              placeholder="https://…/logo.png или /api/public/sites/assets/…"
              autoComplete="off"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={!siteId || logoUploading}
              className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm font-medium text-slate-100 hover:bg-slate-700 disabled:opacity-50 sm:w-auto"
            >
              <Upload className="h-4 w-4" aria-hidden />
              Загрузить логотип
            </button>
          </div>
        </Field>
        {isMisSite ? (
          <div className="rounded-xl border border-slate-700/80 bg-slate-950/40 p-3">
            <div className="text-xs font-medium text-slate-300">Иконка логотипа (медицинская)</div>
            <p className="mt-1 text-[11px] leading-snug text-slate-500">
              Если выбрана иконка, в Mini App в шапке показывается она (приоритетнее картинки по URL). Нажмите снова для сброса.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {MIS_LOGO_ICON_OPTIONS.map(({ id, label }) => {
                const selected = (form.contacts?.mis_logo_icon || "").trim() === id;
                return (
                  <button
                    key={id}
                    type="button"
                    title={label}
                    onClick={() => {
                      if (selected) setContactField("mis_logo_icon", "");
                      else setContactField("mis_logo_icon", id);
                    }}
                    className={[
                      "inline-flex h-11 w-11 items-center justify-center rounded-xl border transition-colors",
                      selected
                        ? "border-emerald-500 bg-emerald-600/20 text-emerald-200"
                        : "border-slate-600 bg-slate-800/80 text-slate-300 hover:border-slate-500 hover:bg-slate-800",
                    ].join(" ")}
                  >
                    <MisLogoIcon iconKey={id} size={22} className="shrink-0" />
                    <span className="sr-only">{label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
        <Field label="Цвет темы" hint="HEX-код, используется как акцент в Mini App.">
          <div className="mt-1 flex flex-col gap-3">
            <div className="flex items-center gap-3">
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
            {isMisSite ? (
              <div className="space-y-1.5">
                <div className="text-xs text-slate-500">Медицинская палитра</div>
                <MedicalColorPresetRow
                  value={form.theme_color}
                  onChange={(hex) => setForm((p) => ({ ...p, theme_color: hex }))}
                />
              </div>
            ) : null}
          </div>
        </Field>
        <Field
          label="Ссылка на оплату"
          hint="Для организации — своя ссылка (например https://sberbank.ru/qr/?uuid=…). Кнопка «QR Сбер» в редакторе страницы подставляет это значение в блок."
        >
          <input
            type="text"
            value={form.contacts?.payment_url || ""}
            onChange={(e) => setContactField("payment_url", e.target.value)}
            className={inputClass}
            maxLength={1024}
            placeholder="https://sberbank.ru/qr/?uuid=…"
            autoComplete="off"
          />
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
        <button type="submit" disabled={saving} className={BTN_SAVE}>
          <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
          {saving ? "Сохранение…" : "Сохранить настройки"}
        </button>
      </div>
    </form>
  );
}

function PagesTab({
  pages,
  loading,
  onCreate,
  onOpen,
  onDelete,
  onChangeOrder,
  onTogglePublished,
  isMisSite = false,
  misRoleTab = "doctor",
  setMisRoleTab,
}) {
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm text-slate-400">
          Порядок отображения задаётся полем «порядок» — меньше число, выше в меню.
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isMisSite ? (
            <div className="flex flex-wrap items-center gap-1 rounded-lg border border-slate-700 bg-slate-950/50 px-2 py-1">
              <span className="text-[11px] text-slate-500">Раздел:</span>
              <button
                type="button"
                onClick={() => setMisRoleTab?.("doctor")}
                className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                  misRoleTab === "doctor"
                    ? "bg-emerald-600 text-white"
                    : "text-slate-300 hover:bg-slate-800"
                }`}
              >
                Врач
              </button>
              <button
                type="button"
                onClick={() => setMisRoleTab?.("patient")}
                className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                  misRoleTab === "patient"
                    ? "bg-emerald-600 text-white"
                    : "text-slate-300 hover:bg-slate-800"
                }`}
              >
                Пациент
              </button>
            </div>
          ) : null}
          <button
            type="button"
            onClick={onCreate}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500"
          >
            <Plus className={ICON_BTN} strokeWidth={2} aria-hidden />
            Новая страница
          </button>
        </div>
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

function MisPageKindHints({ pageKind }) {
  const pk = String(pageKind || "").toLowerCase();
  const text =
    pk === "document_reader"
      ? "Текст из модуля «Читатель» (книги, главы, стихи). Ниже — необязательное HTML-вступление."
      : pk === "mis_patients"
      ? "В Mini App — список пациентов врача при совпадении chat_id с профилем. Ниже — вступительный HTML над списком."
      : pk === "mis_doctor_card"
        ? "Подсказка врачу: полный доступ к карте — например через раздел «Пациенты». Ниже — необязательное HTML-вступление."
        : pk === "mis_patient_card"
          ? "Сводка по карте: ФИО, контакты, последние обследования. HTML — над блоком."
          : pk === "mis_patient_profile"
            ? "Редактирование профиля пациента при входе по MAX. HTML — над формой."
            : pk === "mis_patient_diary"
              ? "Дневник показателей (отправка врачу). HTML — над формой."
              : pk === "mis_patient_tips"
                ? "Статические рекомендации; HTML — над списком."
                : null;
  if (!text) return null;
  return <p className="mt-3 text-[12px] leading-snug text-slate-400">{text}</p>;
}

function misPageEditorContentLabel(pageKind, isMisSite, misAudiencePatient) {
  if (!isMisSite) {
    const pk = String(pageKind || "").toLowerCase();
    if (pk === "booking") return "Текст над формой записи (необязательно)";
    if (pk === "document_reader") return "Вступление (HTML) над текстом читалки (необязательно)";
    if (pk === "profile") return "Вступительный текст (HTML) над датой рождения (необязательно)";
    return "Контент";
  }
  const pk = coerceMisPageKindForAudience(pageKind, misAudiencePatient);
  if (pk === "document_reader") return "Вступление (HTML) над читалкой (необязательно)";
  if (pk === "mis_patients") return "Вступительный текст (HTML) над списком пациентов";
  if (pk === "mis_doctor_card") return "Вступительный текст (HTML) для экрана «Карта пациента»";
  return "Вступительный текст (HTML) над разделом";
}

function PageEditorTab({
  page,
  form,
  setForm,
  portalUsers,
  documentsList = [],
  paymentLinkDefault,
  onSave,
  saving,
  onDelete,
  onBackToList,
  isMisSite = false,
  misAudiencePatient = false,
}) {
  const [isHtmlMode, setIsHtmlMode] = useState(false);

  const insertSberDonationBlock = () => {
    const fromSettings = (paymentLinkDefault || "").trim();
    const preset = fromSettings || SBER_DONATION_DEFAULT_HREF;
    const raw = window.prompt(
      "Ссылка в QR и при нажатии (по умолчанию из «Настроек» сайта; при необходимости измените):",
      preset,
    );
    if (raw === null) return;
    const href = String(raw).trim() || preset;
    const block = buildSberQrDonationBlockHtml({ href });
    setForm((p) => ({
      ...p,
      content: `${(p.content || "").trim()}\n\n${block}\n`.trim(),
    }));
    if (!isHtmlMode) setIsHtmlMode(true);
  };

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

      <div className="rounded-lg border border-slate-600 bg-slate-950/40 p-4">
        {isMisSite ? (
          <>
            <Field
              label="Тип страницы"
              hint="Соответствует выбранной роли МИС в настройках сайта (вкладка «Настройки»)."
            >
              <select
                value={coerceMisPageKindForAudience(form.page_kind, misAudiencePatient)}
                onChange={(e) => {
                  const v = e.target.value;
                  setForm((p) => ({
                    ...p,
                    page_kind: v,
                    booking_staff_user_id: "",
                    embed_module: "",
                    linked_document_id: v === "document_reader" ? p.linked_document_id : "",
                    mis_audience:
                      v === "document_reader"
                        ? misAudiencePatient
                          ? "patient"
                          : "doctor"
                        : p.mis_audience,
                  }));
                }}
                className={`${inputClass} max-w-lg`}
              >
                {misAudiencePatient ? (
                  <>
                    <option value="mis_patient_card">Карта</option>
                    <option value="mis_patient_profile">Профиль</option>
                    <option value="mis_patient_diary">Дневник здоровья</option>
                    <option value="mis_patient_tips">Полезные материалы</option>
                    <option value="document_reader">Читатель (документ)</option>
                  </>
                ) : (
                  <>
                    <option value="mis_patients">Пациенты</option>
                    <option value="mis_doctor_card">Карта пациента</option>
                    <option value="document_reader">Читатель (документ)</option>
                  </>
                )}
              </select>
            </Field>
            <MisPageKindHints pageKind={coerceMisPageKindForAudience(form.page_kind, misAudiencePatient)} />
            {(form.page_kind || "").toLowerCase() === "document_reader" ? (
              <div className="mt-3 space-y-3">
                <Field
                  label="Документ из модуля «Читатель»"
                  hint="Создайте документ и загрузите .txt в разделе панели «Читатель»."
                >
                  <select
                    value={form.linked_document_id || ""}
                    onChange={(e) => setForm((p) => ({ ...p, linked_document_id: e.target.value }))}
                    className={`${inputClass} max-w-lg`}
                    required
                  >
                    <option value="">— выберите документ —</option>
                    {(documentsList || []).map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.title}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Аудитория Mini App" hint="Врач или пациент — кто видит пункт меню с этой страницей.">
                  <select
                    value={form.mis_audience === "patient" ? "patient" : "doctor"}
                    onChange={(e) =>
                      setForm((p) => ({
                        ...p,
                        mis_audience: e.target.value === "patient" ? "patient" : "doctor",
                      }))
                    }
                    className={`${inputClass} max-w-md`}
                  >
                    <option value="doctor">Врач</option>
                    <option value="patient">Пациент</option>
                  </select>
                </Field>
              </div>
            ) : null}
          </>
        ) : (
          <>
            <Field label="Тип страницы" hint="«Запись» — виджет выбора времени; «Читатель» — длинный текст из модуля документов.">
              <select
                value={form.page_kind || "content"}
                onChange={(e) => {
                  const v = e.target.value;
                  setForm((p) => ({
                    ...p,
                    page_kind: v,
                    booking_staff_user_id: v === "booking" ? p.booking_staff_user_id : "",
                    embed_module: v === "content" ? p.embed_module : "",
                    linked_document_id: v === "document_reader" ? p.linked_document_id : "",
                  }));
                }}
                className={`${inputClass} max-w-md`}
              >
                <option value="content">Текст и медиа (как обычно)</option>
                <option value="profile">Профиль (дата рождения в Mini App)</option>
                <option value="booking">Запись на приём к сотруднику</option>
                <option value="document_reader">Читатель (документ)</option>
              </select>
            </Field>
            {(form.page_kind || "content") === "document_reader" ? (
              <div className="mt-3">
                <Field
                  label="Документ из модуля «Читатель»"
                  hint="Создайте документ и загрузите .txt в разделе панели «Читатель»."
                >
                  <select
                    value={form.linked_document_id || ""}
                    onChange={(e) => setForm((p) => ({ ...p, linked_document_id: e.target.value }))}
                    className={`${inputClass} max-w-lg`}
                    required
                  >
                    <option value="">— выберите документ —</option>
                    {(documentsList || []).map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.title}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
            ) : null}
            {(form.page_kind || "content") === "booking" ? (
              <div className="mt-3">
                <Field
                  label="Сотрудник"
                  hint="Пользователь панели организации. Ему нужно задать рабочие часы в «Записи»."
                >
                  <select
                    value={form.booking_staff_user_id || ""}
                    onChange={(e) => setForm((p) => ({ ...p, booking_staff_user_id: e.target.value }))}
                    className={`${inputClass} max-w-md`}
                    required
                  >
                    <option value="">— выберите сотрудника —</option>
                    {(portalUsers || [])
                      .filter((u) => u.is_active !== false)
                      .map((u) => (
                        <option key={u.id} value={u.id}>
                          {(u.display_name || u.username || "").trim() || u.id}
                          {u.role ? ` (${u.role})` : ""}
                        </option>
                      ))}
                  </select>
                </Field>
              </div>
            ) : null}
            {(form.page_kind || "content") === "content" ? (
              <div className="mt-3">
                <Field
                  label="Встроенный модуль платформы"
                  hint="Опционально: позже здесь откроется экран раздела (база знаний, формы и т.д.). Сейчас — заглушка в Mini App."
                >
                  <select
                    value={form.embed_module || ""}
                    onChange={(e) => setForm((p) => ({ ...p, embed_module: e.target.value }))}
                    className={`${inputClass} max-w-xl`}
                  >
                    {EMBED_MODULE_OPTIONS.map((o) => (
                      <option key={o.value || "none"} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
            ) : null}
          </>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label className="block text-xs font-medium text-slate-300">
            {misPageEditorContentLabel(form.page_kind, isMisSite, misAudiencePatient)}
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={insertSberDonationBlock}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-600 bg-slate-800/80 px-2.5 py-1 text-[11px] font-medium text-slate-200 hover:bg-slate-700"
              title="SVG QR + ссылка; в MAX открывается через внешний браузер (WebApp.openLink)"
            >
              <QrCode className="h-3.5 w-3.5" aria-hidden />
              QR Сбер (пожертвование)
            </button>
            <button
              type="button"
              onClick={() => setIsHtmlMode(!isHtmlMode)}
              className="text-xs text-emerald-400 hover:text-emerald-300 underline underline-offset-2"
            >
              {isHtmlMode ? "Вернуться в визуальный редактор" : "Редактировать HTML"}
            </button>
          </div>
        </div>
        
        {isHtmlMode ? (
          <textarea
            value={form.content}
            onChange={(e) => setForm((p) => ({ ...p, content: e.target.value }))}
            className={`${inputClass} min-h-[360px] font-mono text-[13px]`}
            maxLength={500000}
            placeholder="<h1>Добро пожаловать</h1>&#10;<p>Описание вашего сервиса…</p>"
          />
        ) : (
          <div className="rounded-lg border border-slate-700 bg-white text-slate-900 overflow-hidden">
            <ReactQuill
              theme="snow"
              value={form.content}
              onChange={(val) => setForm((p) => ({ ...p, content: val }))}
              className="h-[320px] pb-10"
              modules={{
                toolbar: [
                  [{ header: [1, 2, 3, false] }],
                  ["bold", "italic", "underline", "strike", "blockquote"],
                  [{ list: "ordered" }, { list: "bullet" }],
                  ["link", "image"],
                  ["clean"],
                ],
              }}
            />
          </div>
        )}
        <div className="text-[11px] text-slate-500">
          В визуальном редакторе Quill может упростить разметку (в т.ч. ссылки и встроенный SVG). Для оплаты из
          Mini App используйте{" "}
          <code className="rounded bg-slate-800 px-1">https://sberbank.ru/qr/?uuid=…</code> — открытие идёт через
          внешний браузер MAX. Блоки с QR держите в HTML-режиме.
        </div>
      </div>

      <div className="flex justify-end">
        <button type="submit" disabled={saving} className={BTN_SAVE}>
          <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
          {saving ? "Сохранение…" : "Сохранить страницу"}
        </button>
      </div>
    </form>
  );
}

// ============================================================================
// Live-превью Mini App
// ============================================================================

/** Сборка пунктов Tabbar в том же порядке, что и на бэкенде (`nav_items_for_miniapp`). */
function buildPreviewNav(menuItems, publishedPages) {
  const sorted = [...publishedPages].sort(
    (a, b) =>
      (Number(a.order_index) || 0) - (Number(b.order_index) || 0) ||
      String(a.title || "").localeCompare(String(b.title || "")),
  );
  if (!menuItems || menuItems.length === 0) {
    return sorted.filter((p) => p.slug).map((p) => ({ label: p.title, slug: p.slug }));
  }
  const byId = Object.fromEntries(sorted.map((p) => [String(p.id), p]));
  const ordered = [...menuItems].sort(
    (a, b) => (Number(a.order_index) || 0) - (Number(b.order_index) || 0),
  );
  const out = [];
  for (const it of ordered) {
    if (it.is_visible === false) continue;
    const p = byId[String(it.page_id)];
    if (!p || !p.is_published) continue;
    const label = (it.label || "").trim() || p.title;
    if (p.slug) out.push({ label, slug: p.slug });
  }
  if (out.length === 0) {
    return sorted.filter((p) => p.slug).map((p) => ({ label: p.title, slug: p.slug }));
  }
  return out;
}

/** Безопасный hex — для inline-стилей превью (защита от мусора в поле). */
function sanitizeHex(hex, fallback = "#0f172a") {
  if (typeof hex !== "string") return fallback;
  const s = hex.trim();
  return /^#[0-9a-fA-F]{3}$/.test(s) || /^#[0-9a-fA-F]{6}$/.test(s) ? s : fallback;
}

/**
 * Превью Mini App в виде «телефона».
 *
 * Особенности:
 *  - Использует ``form`` (несохранённые настройки сайта) и ``pageForm`` (живой
 *    ввод редактора страницы), чтобы админ видел изменения до нажатия «Сохранить».
 *  - Активная страница выбирается исходя из вкладки:
 *      settings → первая опубликованная,
 *      pages → первая опубликованная,
 *      page-editor → редактируемая страница (с актуальными значениями из pageForm).
 *  - В меню (Tabbar) подставляется title и slug из pageForm для редактируемой
 *    страницы — так видно порядок / публикацию до сохранения.
 *  - Рендер HTML страницы — через ``dangerouslySetInnerHTML`` (контент вводится
 *    внутри компании, тот же способ использует публичный Mini App).
 */
function MiniAppPreview({
  tab,
  form,
  pages,
  editingPageId,
  pageForm,
  isMisSite = false,
  misRoleTab = "doctor",
  setMisRoleTab,
}) {
  const themeColor = sanitizeHex(form?.theme_color, "#0f172a");
  const title = (form?.title || "").trim() || (form?.name || "").trim() || "Mini App";
  const subtitle = (form?.subtitle || "").trim();
  const logoUrlRaw = (form?.logo_url || "").trim();
  const logoSrc = useMemo(() => siteLogoImgSrc(logoUrlRaw), [logoUrlRaw]);
  const misIconKey = (form?.contacts?.mis_logo_icon || "").trim();
  const showMisLogoIcon = isMisSite && isValidMisLogoIconKey(misIconKey);
  const [logoBroken, setLogoBroken] = useState(false);
  useEffect(() => {
    setLogoBroken(false);
  }, [logoSrc]);

  // Подменяем редактируемую страницу в списке живыми значениями формы редактора.
  const liveList = useMemo(() => {
    if (!Array.isArray(pages)) return [];
    if (tab !== "page-editor" || !editingPageId) return pages;
    return pages.map((p) =>
      p.id === editingPageId
        ? {
            ...p,
            title: (pageForm?.title || p.title || "").trim() || p.title,
            slug: (pageForm?.slug || p.slug || "").trim() || p.slug,
            content: pageForm?.content ?? p.content ?? "",
            order_index: Number.isFinite(Number(pageForm?.order_index))
              ? Number(pageForm.order_index)
              : p.order_index,
            is_published: Boolean(pageForm?.is_published ?? p.is_published),
            page_kind: (pageForm?.page_kind || p.page_kind || "content").toLowerCase(),
            booking_staff_user_id:
              (pageForm?.page_kind || "").toLowerCase() === "booking" && pageForm?.booking_staff_user_id
                ? pageForm.booking_staff_user_id
                : (pageForm?.page_kind || "").toLowerCase() === "content"
                  ? null
                  : p.booking_staff_user_id,
            embed_module: (() => {
              const k = (pageForm?.page_kind || p.page_kind || "content").toLowerCase();
              if (k === "booking" || k.startsWith("mis_") || k === "document_reader" || k === "profile")
                return null;
              return (pageForm?.embed_module || "").trim() || null;
            })(),
            linked_document_id: (() => {
              const k = (pageForm?.page_kind || p.page_kind || "content").toLowerCase();
              if (k !== "document_reader") return null;
              const raw = (pageForm?.linked_document_id || "").trim();
              return raw || p.linked_document_id || null;
            })(),
            mis_audience: (() => {
              const k = (pageForm?.page_kind || p.page_kind || "content").toLowerCase();
              if (k !== "document_reader") return p.mis_audience ?? null;
              return pageForm?.mis_audience === "patient" ? "patient" : "doctor";
            })(),
          }
        : p,
    );
  }, [pages, tab, editingPageId, pageForm]);

  const publishedPages = useMemo(() => {
    const aud = misRoleTab === "patient" ? "patient" : "doctor";
    const base = (liveList || [])
      .filter((p) => p.is_published)
      .filter((p) => {
        if (!isMisSite) return true;
        const ma = String(p.mis_audience || "").toLowerCase();
        if (!ma) return true;
        return ma === aud;
      });
    return base
      .slice()
      .sort(
        (a, b) =>
          (Number(a.order_index) || 0) - (Number(b.order_index) || 0) ||
          String(a.title).localeCompare(String(b.title)),
      );
  }, [liveList, isMisSite, misRoleTab]);

  const nav = useMemo(() => {
    const menuItems = isMisSite
      ? misRoleTab === "patient"
        ? form.mis_menu_items_patient
        : form.mis_menu_items_doctor
      : form.menu_items;
    return buildPreviewNav(menuItems, publishedPages);
  }, [
    form.menu_items,
    form.mis_menu_items_doctor,
    form.mis_menu_items_patient,
    isMisSite,
    misRoleTab,
    publishedPages,
  ]);

  const activePage = useMemo(() => {
    if (tab === "page-editor" && editingPageId) {
      const live = liveList.find((p) => p.id === editingPageId);
      if (live) return live;
    }
    const firstSlug = nav[0]?.slug;
    if (firstSlug) {
      const hit = publishedPages.find((p) => p.slug === firstSlug);
      if (hit) return hit;
    }
    return publishedPages[0] || null;
  }, [tab, editingPageId, liveList, publishedPages, nav]);

  const headerBackground = `linear-gradient(135deg, ${themeColor} 0%, ${themeColor}DD 100%)`;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs font-medium text-slate-300">
        <Smartphone className="h-4 w-4 text-slate-400" aria-hidden />
        Предпросмотр Mini App
        <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
          Live
        </span>
        {isMisSite ? (
          <span className="ml-auto flex items-center gap-1">
            <button
              type="button"
              onClick={() => setMisRoleTab?.("doctor")}
              className={`rounded-md px-2 py-0.5 text-[10px] font-medium ${
                misRoleTab === "doctor" ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400"
              }`}
            >
              Врач
            </button>
            <button
              type="button"
              onClick={() => setMisRoleTab?.("patient")}
              className={`rounded-md px-2 py-0.5 text-[10px] font-medium ${
                misRoleTab === "patient" ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400"
              }`}
            >
              Пациент
            </button>
          </span>
        ) : null}
      </div>

      <div className="mx-auto w-full max-w-[340px]">
        <div
          className="relative overflow-hidden rounded-[38px] border border-slate-700 bg-black p-2 shadow-[0_20px_50px_-20px_rgba(0,0,0,0.6)]"
          aria-label="Превью Mini App"
        >
          <div className="pointer-events-none absolute left-1/2 top-1.5 z-10 h-5 w-24 -translate-x-1/2 rounded-full bg-black" />
          <div
            className="relative flex h-[600px] w-full flex-col overflow-hidden rounded-[30px] bg-white"
            style={{ colorScheme: "light" }}
          >
            <div
              className="flex items-center gap-3 px-4 pb-3 pt-6 text-white"
              style={{ background: headerBackground }}
            >
              {showMisLogoIcon ? (
                <div
                  aria-hidden
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/20 text-white"
                >
                  <MisLogoIcon iconKey={misIconKey} size={28} className="text-white" />
                </div>
              ) : logoSrc && !logoBroken ? (
                <img
                  src={logoSrc}
                  alt=""
                  className="h-11 w-11 shrink-0 rounded-xl object-cover"
                  style={{ background: "rgba(255,255,255,0.15)" }}
                  onError={() => setLogoBroken(true)}
                />
              ) : (
                <div
                  aria-hidden
                  className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/20 text-lg font-semibold"
                >
                  {(title || "M").slice(0, 1).toUpperCase()}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <div className="truncate text-[15px] font-semibold leading-tight">{title}</div>
                {subtitle ? (
                  <div className="truncate text-[11px] text-white/85">{subtitle}</div>
                ) : null}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-4">
              {activePage ? (
                <PagePreviewBody page={activePage} />
              ) : publishedPages.length === 0 ? (
                <EmptyPreview
                  title="Нет опубликованных страниц"
                  detail="Создайте страницу во вкладке «Страницы» и включите публикацию."
                />
              ) : (
                <EmptyPreview
                  title="Страница не выбрана"
                  detail="Выберите раздел в нижнем меню."
                />
              )}
            </div>

            <nav className="border-t border-slate-200 bg-white/95 backdrop-blur">
              {nav.length === 0 ? (
                <div className="px-3 py-2 text-center text-[11px] text-slate-400">
                  Меню появится после публикации хотя бы одной страницы
                </div>
              ) : (
                <ul className="flex flex-wrap items-stretch justify-center gap-1 px-1 py-1 [list-style:none]">
                  {nav.map((item) => {
                    const isActive = activePage && activePage.slug === item.slug;
                    return (
                      <li key={item.slug} className="min-w-0 flex-[1_1_auto]" style={{ minWidth: "min(100%,6rem)", maxWidth: "100%" }}>
                        <div
                          className="flex w-full items-center justify-center px-1 py-1.5 text-center text-[11px] leading-snug"
                          style={{
                            color: isActive ? themeColor : "#6b7280",
                            fontWeight: isActive ? 600 : 500,
                          }}
                        >
                          <span className="break-words [overflow-wrap:anywhere]">{item.label || "—"}</span>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </nav>
          </div>
        </div>
      </div>

      <div className="text-[11px] text-slate-500">
        В реальном Mini App цвет темы, шапка и нижнее меню строятся по этим же
        настройкам. Редактируемая страница обновляется прямо во время ввода.
      </div>
    </div>
  );
}

function PagePreviewBody({ page }) {
  const previewContentRef = useMiniAppHtmlLinkDelegate(page?.content, { forceExternal: true });
  const pk = page ? String(page.page_kind || "content").toLowerCase() : "";
  const isBooking =
    page &&
    pk === "booking" &&
    page.booking_staff_user_id;
  const embedKey =
    page && !isBooking && !pk.startsWith("mis_") && pk !== "profile" ? String(page.embed_module || "").trim() : "";

  if (pk === "mis_patients") {
    return (
      <article className="text-slate-800">
        <h2 className="mb-2 text-lg font-semibold text-slate-900">
          {(page.title || "").trim() || "Пациенты"}
        </h2>
        {page.content ? (
          <div
            ref={previewContentRef}
            className="miniapp-preview-content mb-3 space-y-2 text-[14px] leading-relaxed"
            dangerouslySetInnerHTML={{ __html: page.content }}
          />
        ) : null}
        <div className="rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-[13px] text-teal-900">
          Здесь в Mini App — список пациентов врача (доступ только при совпадении{" "}
          <span className="font-medium">chat_id</span> с профилем врача).
        </div>
      </article>
    );
  }

  if (pk === "mis_doctor_card") {
    return (
      <article className="text-slate-800">
        <h2 className="mb-2 text-lg font-semibold text-slate-900">
          {(page.title || "").trim() || "Карта пациента"}
        </h2>
        {page.content ? (
          <div
            ref={previewContentRef}
            className="miniapp-preview-content mb-3 space-y-2 text-[14px] leading-relaxed"
            dangerouslySetInnerHTML={{ __html: page.content }}
          />
        ) : null}
        <div className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-[13px] text-sky-950">
          Экран подсказки врачу: открыть карты через раздел «Пациенты» или веб-МИС.
        </div>
      </article>
    );
  }

  if (["mis_patient_card", "mis_patient_profile", "mis_patient_diary", "mis_patient_tips"].includes(pk)) {
    const hint =
      pk === "mis_patient_card"
        ? "Сводка карты (контакты, обследования)."
        : pk === "mis_patient_profile"
          ? "Профиль пациента."
          : pk === "mis_patient_diary"
            ? "Дневник показателей."
            : "Полезные материалы.";
    return (
      <article className="text-slate-800">
        <h2 className="mb-2 text-lg font-semibold text-slate-900">{(page.title || "").trim() || "Раздел"}</h2>
        {page.content ? (
          <div
            ref={previewContentRef}
            className="miniapp-preview-content mb-3 space-y-2 text-[14px] leading-relaxed"
            dangerouslySetInnerHTML={{ __html: page.content }}
          />
        ) : null}
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-[13px] text-emerald-950">
          {hint} Доступ при роли <span className="font-medium">пациент</span> в Mini App.
        </div>
      </article>
    );
  }

  if (pk === "profile") {
    return (
      <article className="text-slate-800">
        <h2 className="mb-2 text-lg font-semibold text-slate-900">{(page.title || "").trim() || "Профиль"}</h2>
        {page.content ? (
          <div
            ref={previewContentRef}
            className="miniapp-preview-content mb-3 space-y-2 text-[14px] leading-relaxed"
            dangerouslySetInnerHTML={{ __html: page.content }}
          />
        ) : null}
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[13px] text-amber-950">
          В Mini App — выбор даты рождения (календарь) и сохранение в профиле.
        </div>
      </article>
    );
  }

  if (pk === "document_reader") {
    return (
      <article className="text-slate-800">
        <h2 className="mb-2 text-lg font-semibold text-slate-900">{(page.title || "").trim() || "Читатель"}</h2>
        {page.content ? (
          <div
            ref={previewContentRef}
            className="miniapp-preview-content mb-3 space-y-2 text-[14px] leading-relaxed"
            dangerouslySetInnerHTML={{ __html: page.content }}
          />
        ) : null}
        <div className="rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-[13px] text-violet-950">
          {page.linked_document_id
            ? "В Mini App — читалка с оглавлением (книги → главы → стихи)."
            : "Выберите документ в модуле «Читатель»."}
        </div>
      </article>
    );
  }

  return (
    <article className="text-slate-800">
      <h2 className="mb-2 text-lg font-semibold text-slate-900">
        {(page.title || "").trim() || "Без заголовка"}
      </h2>
      {embedKey ? (
        <div className="mb-3 [&_.max-ui-typography-title]:!text-[15px]">
          <MiniAppEmbedPlaceholder moduleKey={embedKey} />
        </div>
      ) : null}
      {isBooking ? (
        <>
          {page.content ? (
            <div
              ref={previewContentRef}
              className="miniapp-preview-content mb-3 space-y-2 text-[14px] leading-relaxed"
              dangerouslySetInnerHTML={{ __html: page.content }}
            />
          ) : null}
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-[13px] text-emerald-900">
            Здесь в Mini App — выбор даты и свободного слота; запись попадает в расписание сотрудника в панели
            («Записи»).
          </div>
        </>
      ) : page.content ? (
        <div
          ref={previewContentRef}
          className="miniapp-preview-content space-y-2 text-[14px] leading-relaxed"
          dangerouslySetInnerHTML={{ __html: page.content }}
        />
      ) : (
        <p className="text-[13px] text-slate-500">Раздел пока пуст.</p>
      )}
    </article>
  );
}

function EmptyPreview({ title, detail }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 text-center text-slate-500">
      <div className="text-sm font-semibold text-slate-700">{title}</div>
      {detail ? <div className="text-xs">{detail}</div> : null}
    </div>
  );
}
