import { Button, Container, Flex, Panel, Spinner, Typography } from "@maxhub/max-ui";
import axios from "axios";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMiniAppAuthStore } from "../../store/miniAppAuthStore.js";
import { useMiniAppConfigStore } from "../../store/miniAppConfigStore.js";
import { useMiniAppMisStore } from "../../store/miniAppMisStore.js";
import { setPatientSession } from "../../utils/patientMisAuth.js";
import { useMiniAppThemeStore } from "../../store/miniAppThemeStore.js";
import { useMiniAppHtmlLinkDelegate } from "../../hooks/useMiniAppHtmlLinkDelegate.js";
import { siteLogoImgSrc } from "../../utils/siteLogoUrl.js";
import { isValidMisLogoIconKey, MisLogoIcon } from "../../utils/misMedicalBranding.jsx";
import { MiniAppBookingContent } from "./MiniAppBookingContent.jsx";
import { MiniAppEmbedPlaceholder } from "./MiniAppEmbedPlaceholder.jsx";
import { MiniAppMisPatientsContent } from "./MiniAppMisPatientsContent.jsx";
import { MiniAppMisDoctorCardContent } from "./MiniAppMisDoctorCardContent.jsx";
import { MiniAppMisPatientScreens } from "./MiniAppMisPatientScreens.jsx";
import { MiniAppStaffPanel } from "./MiniAppStaffPanel.jsx";
import { DocumentReader } from "../../components/miniapp/DocumentReader.jsx";
import {
  getMisMiniappAudience,
  legacyMisPatientsSlugAllowed,
  misSitePageVisibleInNav,
} from "../../utils/misMiniAppNav.js";
import { PAGE_H1, PAGE_TEXT } from "../../styles/pageLayout.js";
import "./miniappPageContent.css";

/** Страница «Профиль»: дата рождения (нативный календарь) и вступительный HTML. */
function MiniAppProfileContent({ page, miniToken, themeColor }) {
  const [birthDate, setBirthDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const introRef = useMiniAppHtmlLinkDelegate(page?.content);

  const accent = (themeColor || "#2563eb").trim() || "#2563eb";

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!miniToken) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setErr("");
      try {
        const { data } = await axios.get("/api/miniapp/me", {
          headers: { Authorization: `Bearer ${miniToken}` },
        });
        if (cancelled) return;
        const raw = data?.birth_date;
        if (raw && String(raw).length >= 10) {
          setBirthDate(String(raw).slice(0, 10));
        } else {
          setBirthDate("");
        }
      } catch {
        if (!cancelled) setErr("Не удалось загрузить данные профиля.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [miniToken]);

  const onSave = async () => {
    if (!miniToken) return;
    setSaving(true);
    setErr("");
    try {
      const body = { birth_date: birthDate ? birthDate : null };
      await axios.patch("/api/miniapp/me", body, {
        headers: { Authorization: `Bearer ${miniToken}` },
      });
    } catch {
      setErr("Не удалось сохранить дату рождения.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ padding: "16px 16px 24px" }}>
      <h2
        style={{
          margin: "0 0 12px",
          fontSize: 20,
          fontWeight: 600,
          lineHeight: 1.3,
          color: "#111827",
        }}
      >
        {(page?.title || "").trim() || "Профиль"}
      </h2>
      {page?.content ? (
        <div
          ref={introRef}
          className="miniapp-page-content mb-4"
          style={{ lineHeight: 1.55, fontSize: 15, color: "#1f2937" }}
          dangerouslySetInnerHTML={{ __html: page.content }}
        />
      ) : null}
      {loading ? (
        <Typography.Body style={{ color: "#6b7280" }}>Загрузка…</Typography.Body>
      ) : (
        <div className="space-y-3" style={{ maxWidth: 360 }}>
          {err ? (
            <Typography.Body style={{ color: "#b91c1c" }}>{err}</Typography.Body>
          ) : null}
          <label style={{ display: "block" }}>
            <span style={{ display: "block", fontSize: 13, color: "#374151", marginBottom: 6 }}>Дата рождения</span>
            <input
              type="date"
              value={birthDate}
              onChange={(e) => setBirthDate(e.target.value)}
              max="2100-12-31"
              style={{
                width: "100%",
                maxWidth: 280,
                padding: "10px 12px",
                fontSize: 16,
                borderRadius: 8,
                border: "1px solid #e5e7eb",
                color: "#111827",
                background: "#fff",
              }}
            />
          </label>
          <Button
            onClick={onSave}
            disabled={saving}
            size="m"
            style={{ background: accent, borderColor: accent }}
            mode="primary"
            title="Сохранить дату рождения"
          >
            {saving ? "Сохранение…" : "Сохранить"}
          </Button>
        </div>
      )}
    </div>
  );
}

/** Нижнее меню МИС по роли (если в конфиге задано отдельно). */
function pickMisNavForRole(cfg, role) {
  if (!cfg || cfg.site_kind !== "mis" || !role) return null;
  if (role === "doctor" && Array.isArray(cfg.mis_nav_items_doctor) && cfg.mis_nav_items_doctor.length > 0) {
    return cfg.mis_nav_items_doctor;
  }
  if (role === "patient" && Array.isArray(cfg.mis_nav_items_patient) && cfg.mis_nav_items_patient.length > 0) {
    return cfg.mis_nav_items_patient;
  }
  return null;
}

/**
 * Отступ снизу у области прокрутки: нижнее меню (`MiniAppTabbar`) с `position: fixed`
 * не участвует в потоке — без достаточного padding последние блоки страницы оказываются под таббаром.
 * ~48px одна строка чипов + запас на перенос на вторую строку + safe-area.
 */
const MINIAPP_TABBAR_SCROLL_PAD =
  "calc(env(safe-area-inset-bottom, 0px) + max(120px, min(28vh, 200px)))";

/**
 * Извлекает строку ``init_data`` из параметров запуска Mini App мессенджера MAX.
 *
 * Согласно документации MAX (https://dev.max.ru/docs/webapps/validation) стартовые
 * параметры передаются в URL-фрагменте в поле ``WebAppData``:
 *
 *     https://example.com/inn/1234#WebAppData=<urlencoded>&WebAppPlatform=web&WebAppVersion=26.2.8
 *
 * Клиент обязан передать на бэкенд ИМЕННО содержимое ``WebAppData`` (один раз URL-
 * декодированное — это автоматически делает ``URLSearchParams.get``). Именно по этой
 * строке бэкенд считает HMAC-SHA256 и проверяет поле ``hash``.
 *
 * Порядок поиска (в порядке приоритета):
 *   1. ``window.WebApp.initData`` — официальный MAX Bridge; содержит уже готовую
 *      строку ``WebAppData``.
 *   2. URL-фрагмент (``window.location.hash``), ключ ``WebAppData``.
 *   3. Совместимость с Telegram-стилем (``tgWebAppData``/``initData``) и явный
 *      query-param ``?init_data=…`` — пригодится для E2E тестов и прежних клиентов.
 *   4. Dev-fallback ``?chat_id=…`` для браузерной отладки (подпись будет невалидна —
 *      бэкенд отдаст 401/403, но это ожидаемо вне мессенджера).
 */
function extractInitData(searchParams) {
  const winAny = typeof window !== "undefined" ? window : {};

  const fromMaxBridge =
    winAny?.WebApp?.initData ||
    winAny?.MaxWebApp?.initData ||
    winAny?.maxWebApp?.initData ||
    winAny?.TelegramWebApp?.initData ||
    winAny?.Telegram?.WebApp?.initData ||
    "";
  if (typeof fromMaxBridge === "string" && fromMaxBridge.trim()) {
    return fromMaxBridge.trim();
  }

  const rawHash =
    typeof window !== "undefined" ? (window.location.hash || "").replace(/^#/, "") : "";
  if (rawHash) {
    let hashParams = null;
    try {
      hashParams = new URLSearchParams(rawHash);
    } catch {
      hashParams = null;
    }
    if (hashParams) {
      const webAppData = hashParams.get("WebAppData");
      if (webAppData && webAppData.trim()) return webAppData.trim();
      const tgLike =
        hashParams.get("tgWebAppData") ||
        hashParams.get("initData") ||
        hashParams.get("init_data") ||
        "";
      if (tgLike && tgLike.trim()) return tgLike.trim();
    }
    if (/=/.test(rawHash) && /\bhash=/.test(rawHash)) {
      return rawHash;
    }
  }

  const fromQuery =
    searchParams.get("init_data") ||
    searchParams.get("initData") ||
    searchParams.get("tgWebAppData") ||
    searchParams.get("WebAppData") ||
    "";
  if (fromQuery) return fromQuery;

  const devChatId = searchParams.get("chat_id");
  if (devChatId) {
    const name = searchParams.get("name") || "";
    const params = new URLSearchParams();
    params.set("chat_id", devChatId);
    if (name) params.set("name", name);
    return params.toString();
  }
  return "";
}

/** HEX → rgba() для полупрозрачных кнопок меню. */
function hexToRgba(hex, alpha) {
  if (typeof hex !== "string" || alpha < 0 || alpha > 1) return `rgba(99, 102, 241, ${alpha})`;
  const s = hex.trim().replace(/^#/, "");
  if (!/^[0-9a-fA-F]{3}$/.test(s) && !/^[0-9a-fA-F]{6}$/.test(s)) return `rgba(99, 102, 241, ${alpha})`;
  const full = s.length === 3 ? s.split("").map((c) => c + c).join("") : s;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function StatusScreen({ children }) {
  return (
    <Panel mode="secondary" style={{ minHeight: "100%" }}>
      <Container>
        <Flex
          direction="column"
          align="center"
          justify="center"
          gap={16}
          style={{ minHeight: "100dvh", padding: "32px 16px", textAlign: "center" }}
        >
          {children}
        </Flex>
      </Container>
    </Panel>
  );
}

function LoadingScreen({ label }) {
  return (
    <StatusScreen>
      <Spinner size="large" />
      <Typography.Title>Входим в приложение…</Typography.Title>
      {label ? <Typography.Body>{label}</Typography.Body> : null}
    </StatusScreen>
  );
}

function ErrorScreen({ title, detail, onRetry }) {
  return (
    <StatusScreen>
      <Typography.Title>{title}</Typography.Title>
      {detail ? <Typography.Body>{detail}</Typography.Body> : null}
      {onRetry ? (
        <Button mode="primary" onClick={onRetry}>
          Повторить
        </Button>
      ) : null}
    </StatusScreen>
  );
}

/**
 * Нижняя навигация: сегментированные «кнопки» (чипы) с акцентом бренда.
 * Высоту блока правьте здесь; таббар fixed к низу экрана (зазор снизу в WebView MAX).
 * При смене высоты синхронизируйте MINIAPP_TABBAR_SCROLL_PAD в этом файле.
 */
function MiniAppTabbar({ items, activeSlug, onChange, themeColor }) {
  if (!items || items.length === 0) return null;
  const accent = themeColor && themeColor.trim() ? themeColor.trim() : "#4f46e5";
  return (
    <nav
      aria-label="Навигация Mini App"
      style={{
        position: "fixed",
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 100,
        boxSizing: "border-box",
        backdropFilter: "blur(12px)",
        background: "linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(248,250,252,0.98) 100%)",
        borderTop: "1px solid rgba(15, 23, 42, 0.08)",
        boxShadow: "0 -2px 16px rgba(15, 23, 42, 0.05)",
        paddingTop: 4,
        paddingLeft: "max(8px, env(safe-area-inset-left, 0px))",
        paddingRight: "max(8px, env(safe-area-inset-right, 0px))",
        paddingBottom: "calc(4px + env(safe-area-inset-bottom, 0px))",
      }}
    >
      <ul
        style={{
          display: "flex",
          flexWrap: "wrap",
          listStyle: "none",
          listStyleType: "none",
          margin: 0,
          padding: 0,
          gap: 4,
          rowGap: 2,
          justifyContent: "center",
          alignItems: "stretch",
        }}
        className="miniapp-tabbar-scroll"
      >
        {items.map((item) => {
          const active = item.slug === activeSlug;
          return (
            <li
              key={item.slug}
              style={{
                flex: "1 1 auto",
                minWidth: "min(100%, 6rem)",
                maxWidth: "100%",
                listStyle: "none",
                listStyleType: "none",
              }}
            >
              <button
                type="button"
                onClick={() => onChange(item.slug)}
                aria-current={active ? "page" : undefined}
                style={{
                  width: "100%",
                  minHeight: 40,
                  padding: "4px 8px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  borderRadius: 9,
                  border: active
                    ? `1.5px solid ${hexToRgba(accent, 0.55)}`
                    : "1.5px solid rgba(15, 23, 42, 0.1)",
                  background: active ? hexToRgba(accent, 0.16) : "rgba(255, 255, 255, 0.9)",
                  color: active ? accent : "#475569",
                  fontWeight: active ? 700 : 600,
                  fontSize: 14,
                  lineHeight: 1.4,
                  letterSpacing: active ? "-0.01em" : "0",
                  boxShadow: active
                    ? `0 2px 8px ${hexToRgba(accent, 0.22)}, inset 0 1px 0 rgba(255,255,255,0.85)`
                    : "0 1px 3px rgba(15, 23, 42, 0.07), inset 0 1px 0 rgba(255,255,255,0.95)",
                  transition: "background 0.18s ease, color 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease, transform 0.12s ease",
                  WebkitTapHighlightColor: "transparent",
                }}
              >
                <span
                  style={{
                    textAlign: "center",
                    whiteSpace: "normal",
                    overflowWrap: "anywhere",
                    wordBreak: "break-word",
                  }}
                >
                  {item.label}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/**
 * Шапка Mini App. Заголовок и подзаголовок — из конфига сайта, акцент — theme_color.
 */
function MiniAppHeader({ title, subtitle, logoUrl, themeColor, logoIconKey }) {
  const rawIcon = typeof logoIconKey === "string" ? logoIconKey.trim() : "";
  const showMisIcon = isValidMisLogoIconKey(rawIcon);
  const logoSrc = useMemo(() => siteLogoImgSrc(logoUrl), [logoUrl]);
  const [logoBroken, setLogoBroken] = useState(false);
  useEffect(() => {
    setLogoBroken(false);
  }, [logoSrc]);

  const background = themeColor
    ? `linear-gradient(135deg, ${themeColor} 0%, ${themeColor}DD 100%)`
    : "var(--max-color-primary, #0f172a)";
  /* Обычный header вместо Panel: у Panel в max-ui часто flex-grow:1 — шапка съедала весь экран. */
  return (
    <header
      style={{
        flexShrink: 0,
        flexGrow: 0,
        boxSizing: "border-box",
        padding: "16px",
        borderBottom: "1px solid rgba(0,0,0,0.08)",
        background,
        color: "#fff",
      }}
    >
      <Flex align="center" gap={12}>
        {showMisIcon ? (
          <div
            aria-hidden
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: "rgba(255,255,255,0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
            }}
          >
            <MisLogoIcon iconKey={rawIcon} size={26} strokeWidth={1.75} />
          </div>
        ) : logoSrc && !logoBroken ? (
          <img
            src={logoSrc}
            alt=""
            onError={() => setLogoBroken(true)}
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              objectFit: "cover",
              background: "rgba(255,255,255,0.15)",
            }}
          />
        ) : (
          <div
            aria-hidden
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: "rgba(255,255,255,0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 20,
              fontWeight: 600,
              color: "#fff",
            }}
          >
            {(title || "M").slice(0, 1).toUpperCase()}
          </div>
        )}
        <Flex direction="column" gap={2} style={{ minWidth: 0, flex: 1 }}>
          <div
            style={{
              color: "#fff",
              margin: 0,
              fontSize: 18,
              fontWeight: 600,
              lineHeight: 1.25,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {title || "Mini App"}
          </div>
          {subtitle ? (
            <div style={{ color: "rgba(255,255,255,0.9)", fontSize: 13, lineHeight: 1.35 }}>
              {subtitle}
            </div>
          ) : null}
        </Flex>
      </Flex>
    </header>
  );
}

/**
 * Отрисовка контента страницы (HTML/Markdown из CMS).
 *
 * Сейчас используется `dangerouslySetInnerHTML`, т.к. контент вводят внутри
 * компании (не UGC) и рендерится в нативном WebView мессенджера. Клики по ссылкам
 * ведут через WebApp.openLink (внешний браузер), см. useMiniAppHtmlLinkDelegate.
 */
function MiniAppPageContent({ page, organizationId, miniToken, misRole, themeColor }) {
  const contentRef = useMiniAppHtmlLinkDelegate(page?.content);
  const pk = page ? String(page.page_kind || "content").toLowerCase() : "";
  const isBooking =
    page && pk === "booking" && page.booking_staff_user_id;
  const isMisBuiltIn =
    pk === "mis_patients" ||
    pk === "mis_doctor_card" ||
    pk.startsWith("mis_patient_");
  const embedKey =
    page && !isBooking && !isMisBuiltIn && pk !== "profile"
      ? String(page.embed_module || "").trim()
      : "";

  if (!page) {
    return (
      <div style={{ padding: "32px 16px", textAlign: "center" }}>
        <Typography.Title>Страница не выбрана</Typography.Title>
        <div style={{ marginTop: 8 }}>
          <Typography.Body>Выберите раздел в нижнем меню.</Typography.Body>
        </div>
      </div>
    );
  }

  if (pk === "mis_patients") {
    return (
      <MiniAppMisPatientsContent
        miniToken={miniToken}
        misRole={misRole}
        pageTitle={page.title}
        introHtml={page.content}
        themeColor={themeColor}
      />
    );
  }

  if (pk === "mis_doctor_card") {
    return (
      <MiniAppMisDoctorCardContent pageTitle={page.title} introHtml={page.content} themeColor={themeColor} />
    );
  }

  if (
    pk === "mis_patient_card" ||
    pk === "mis_patient_profile" ||
    pk === "mis_patient_diary" ||
    pk === "mis_patient_tips"
  ) {
    return (
      <MiniAppMisPatientScreens
        pageKind={pk}
        pageTitle={page.title}
        introHtml={page.content}
        themeColor={themeColor}
      />
    );
  }

  if (pk === "profile") {
    return <MiniAppProfileContent page={page} miniToken={miniToken} themeColor={themeColor} />;
  }

  if (pk === "document_reader") {
    if (!page.linked_document_id) {
      return (
        <div style={{ padding: "24px 16px" }}>
          <Typography.Body style={{ color: "#b91c1c" }}>
            Страница «Читатель» без привязанного документа. Укажите документ в конструкторе сайта.
          </Typography.Body>
        </div>
      );
    }
    return (
      <DocumentReader
        documentId={page.linked_document_id}
        pageTitle={page.title}
        introHtml={(page.content || "").trim() ? page.content : undefined}
        themeColor={themeColor}
      />
    );
  }

  return (
    <div style={{ padding: "16px 16px 24px" }}>
      {/*
        Не используем Typography.Title для заголовка страницы: в MAX UI это часто
        «display»-уровень и тянет accent (theme_color), визуально перекрывая контент.
      */}
      <h2
        style={{
          margin: "0 0 12px",
          fontSize: 20,
          fontWeight: 600,
          lineHeight: 1.3,
          color: "#111827",
        }}
      >
        {(page.title || "").trim() || "Страница"}
      </h2>
      {isBooking && organizationId ? (
        <MiniAppBookingContent
          organizationId={organizationId}
          staffUserId={page.booking_staff_user_id}
          introHtml={(page.content || "").trim() ? page.content : undefined}
        />
      ) : isBooking && !organizationId ? (
        <p style={{ margin: 0, fontSize: 15, color: "#b91c1c" }}>
          Запись недоступна: нет данных организации.
        </p>
      ) : embedKey ? (
        <>
          <MiniAppEmbedPlaceholder moduleKey={embedKey} />
          {page.content ? (
            <div
              ref={contentRef}
              className="miniapp-page-content"
              style={{
                lineHeight: 1.55,
                fontSize: 15,
                color: "#1f2937",
              }}
              dangerouslySetInnerHTML={{ __html: page.content }}
            />
          ) : (
            <p style={{ margin: 0, fontSize: 15, color: "#6b7280" }}>Раздел пока пуст.</p>
          )}
        </>
      ) : page.content ? (
        <div
          ref={contentRef}
          className="miniapp-page-content"
          style={{
            lineHeight: 1.55,
            fontSize: 15,
            color: "#1f2937",
          }}
          dangerouslySetInnerHTML={{ __html: page.content }}
        />
      ) : (
        <p style={{ margin: 0, fontSize: 15, color: "#6b7280" }}>Раздел пока пуст.</p>
      )}
    </div>
  );
}

/**
 * Точка входа публичного Mini App (`/inn/:inn`):
 *  1) авторизует по `chat_id` (POST /api/miniapp/auth),
 *  2) подтягивает конфиг сайта (GET /api/public/miniapp/config/{inn}),
 *  3) применяет `theme_color` через `useMiniAppThemeStore` (CSS-переменные),
 *  4) рендерит активную страницу + нижнее меню (Tabbar).
 */
export function MiniAppEntryPage() {
  const { inn } = useParams();
  const [searchParams] = useSearchParams();
  const setAuth = useMiniAppAuthStore((s) => s.setAuth);
  const clearAuth = useMiniAppAuthStore((s) => s.clearAuth);
  const miniToken = useMiniAppAuthStore((s) => s.token);

  const config = useMiniAppConfigStore((s) => s.config);
  const setConfig = useMiniAppConfigStore((s) => s.setConfig);
  const resetConfig = useMiniAppConfigStore((s) => s.reset);
  const resetMis = useMiniAppMisStore((s) => s.reset);
  const setMisSession = useMiniAppMisStore((s) => s.setMisSession);
  const setPatientToken = useMiniAppMisStore((s) => s.setPatientToken);

  const setThemeColor = useMiniAppThemeStore((s) => s.setThemeColor);

  const misSession = useMiniAppMisStore((s) => s.misSession);
  const misPatientToken = useMiniAppMisStore((s) => s.patientToken);

  const [status, setStatus] = useState("loading");
  const [errorTitle, setErrorTitle] = useState("");
  const [errorDetail, setErrorDetail] = useState("");
  const [activeSlug, setActiveSlug] = useState(null);
  const [staffMenu, setStaffMenu] = useState(false);
  const startedRef = useRef(false);

  const initData = useMemo(() => extractInitData(searchParams), [searchParams]);

  const bootstrap = useCallback(async () => {
    setStatus("loading");
    setErrorTitle("");
    setErrorDetail("");
    resetConfig();
    resetMis();
    setThemeColor(null);

    if (!inn || !String(inn).trim()) {
      setStatus("error");
      setErrorTitle("ИНН организации не указан в ссылке");
      setErrorDetail("Откройте Mini App по ссылке вида https://lotus-it.ru/inn/<ИНН>.");
      return;
    }
    if (!initData) {
      setStatus("error");
      setErrorTitle("Не удалось прочитать данные авторизации мессенджера");
      setErrorDetail(
        "Откройте приложение из бота MAX (кнопка Web App). Параметры запуска должны включать chat_id.",
      );
      return;
    }

    let authData = null;
    try {
      const authResp = await axios.post("/api/miniapp/auth", {
        inn: String(inn).trim(),
        init_data: initData,
      });
      authData = authResp.data;
      setAuth({
        token: authData.access_token,
        userId: authData.user_id,
        organizationId: authData.organization_id,
        chatId: authData.chat_id,
        name: authData.name,
      });
    } catch (e) {
      clearAuth();
      setStatus("error");
      const detail = e?.response?.data?.detail || e?.message || "Неизвестная ошибка";
      if (e?.response?.status === 404) {
        setErrorTitle("Организация не найдена");
      } else if (e?.response?.status === 401) {
        setErrorTitle("Не удалось подтвердить данные авторизации");
      } else {
        setErrorTitle("Не удалось войти в Mini App");
      }
      setErrorDetail(typeof detail === "string" ? detail : JSON.stringify(detail));
      return;
    }

    try {
      const { data: cfg } = await axios.get(
        `/api/public/miniapp/config/${encodeURIComponent(String(inn).trim())}`,
      );
      setConfig(cfg);
      if (cfg?.theme_color) setThemeColor(cfg.theme_color);

      let misRoleFromSession = null;
      if (cfg?.site_kind === "mis" && authData?.access_token) {
        try {
          const { data: sess } = await axios.get("/api/miniapp/mis/session", {
            headers: { Authorization: `Bearer ${authData.access_token}` },
          });
          setMisSession(sess);
          misRoleFromSession = sess?.role ?? null;
          if (sess?.role === "patient") {
            const { data: boot } = await axios.post(
              "/api/miniapp/mis/patient-bootstrap",
              {},
              { headers: { Authorization: `Bearer ${authData.access_token}` } },
            );
            if (boot?.access_token) {
              setPatientToken(boot.access_token);
              setPatientSession(boot.access_token, boot.patient_id, authData.organization_id);
            }
          }
        } catch {
          setMisSession(null);
        }
      }
      const pgs = Array.isArray(cfg?.pages) ? cfg.pages : [];
      const misNavPick = pickMisNavForRole(cfg, misRoleFromSession);
      const nav = misNavPick
        ? misNavPick.filter((x) => x && x.slug)
        : Array.isArray(cfg?.nav_items) && cfg.nav_items.length > 0
          ? cfg.nav_items.filter((x) => x && x.slug)
          : pgs.map((p) => ({ label: p.title, slug: p.slug }));
      const audience = getMisMiniappAudience(cfg?.contacts);
      const navForUser = nav.filter((it) => {
        const pg = pgs.find((p) => p.slug === it.slug);
        if (!pg) return false;
        if (cfg?.site_kind !== "mis") {
          return legacyMisPatientsSlugAllowed(pg, misRoleFromSession);
        }
        return misSitePageVisibleInNav(pg, audience, misRoleFromSession);
      });
      const firstSlug =
        navForUser[0]?.slug ??
        pgs.find((p) =>
          cfg?.site_kind === "mis"
            ? misSitePageVisibleInNav(p, audience, misRoleFromSession)
            : legacyMisPatientsSlugAllowed(p, misRoleFromSession),
        )?.slug ??
        pgs[0]?.slug ??
        null;
      setActiveSlug(firstSlug);
      setStatus("ready");
    } catch (e) {
      setStatus("error");
      const detail = e?.response?.data?.detail || e?.message || "Неизвестная ошибка";
      if (e?.response?.status === 404) {
        setErrorTitle("Контент Mini App ещё не настроен");
      } else {
        setErrorTitle("Не удалось загрузить контент Mini App");
      }
      setErrorDetail(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
  }, [inn, initData, setAuth, clearAuth, setConfig, resetConfig, setThemeColor, resetMis, setMisSession, setPatientToken]);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    return () => {
      setThemeColor(null);
    };
  }, [setThemeColor]);

  useEffect(() => {
    if (status !== "ready" || !miniToken) {
      setStaffMenu(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await axios.get("/api/miniapp/staff/session", {
          headers: { Authorization: `Bearer ${miniToken}` },
        });
        if (!cancelled) setStaffMenu(Boolean(data?.is_staff));
      } catch {
        if (!cancelled) setStaffMenu(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [status, miniToken]);

  // Важно: хуки только до любых return — иначе при смене status (loading → ready)
  // меняется число вызовов useMemo и React падает (часто — пустой тёмный экран в WebView).
  const misAudience = useMemo(() => getMisMiniappAudience(config?.contacts), [config?.contacts]);

  const pages = useMemo(() => {
    const all = Array.isArray(config?.pages) ? config.pages : [];
    if (config?.site_kind !== "mis" || !misSession?.role) return all;
    return all.filter((p) => misSitePageVisibleInNav(p, misAudience, misSession.role));
  }, [config?.pages, config?.site_kind, misSession?.role, misAudience]);

  const navItems = useMemo(() => {
    const misNav = pickMisNavForRole(config, misSession?.role);
    const raw = misNav ?? config?.nav_items;
    const base =
      Array.isArray(raw) && raw.length > 0
        ? raw.filter((x) => x && x.slug)
        : pages.map((p) => ({ label: p.title, slug: p.slug }));
    return base.filter((it) => {
      const pg = pages.find((p) => p.slug === it.slug);
      if (!pg) return false;
      if (config?.site_kind !== "mis") {
        return legacyMisPatientsSlugAllowed(pg, misSession?.role);
      }
      return misSitePageVisibleInNav(pg, misAudience, misSession?.role);
    });
  }, [
    config,
    config?.nav_items,
    config?.mis_nav_items_doctor,
    config?.mis_nav_items_patient,
    config?.site_kind,
    pages,
    misSession?.role,
    misAudience,
  ]);

  const navItemsWithStaff = useMemo(() => {
    if (!staffMenu) return navItems;
    if (navItems.some((x) => x.slug === "__staff__")) return navItems;
    return [...navItems, { label: "Управление", slug: "__staff__" }];
  }, [navItems, staffMenu]);

  useEffect(() => {
    if (status !== "ready") return;
    if (!staffMenu && activeSlug === "__staff__") {
      const first = navItems[0]?.slug ?? pages[0]?.slug ?? null;
      if (first) setActiveSlug(first);
    }
  }, [status, staffMenu, activeSlug, navItems, pages]);

  useEffect(() => {
    if (status !== "ready" || activeSlug === "__staff__" || !activeSlug) return;
    const allowed = new Set(navItems.map((x) => x.slug));
    if (!allowed.has(activeSlug) && navItems[0]?.slug) {
      setActiveSlug(navItems[0].slug);
    }
  }, [status, navItems, activeSlug]);

  useEffect(() => {
    if (status !== "ready") return;
    if (staffMenu && pages.length === 0 && activeSlug !== "__staff__") {
      setActiveSlug("__staff__");
    }
  }, [status, staffMenu, pages.length, activeSlug]);

  if (status === "loading") {
    return <LoadingScreen label="Загружаем содержимое…" />;
  }
  if (status === "error") {
    return <ErrorScreen title={errorTitle} detail={errorDetail} onRetry={bootstrap} />;
  }

  const activePage =
    activeSlug === "__staff__"
      ? null
      : pages.find((p) => p.slug === activeSlug) || (pages.length > 0 ? pages[0] : null);
  const themeColor = config?.theme_color || null;

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        width: "100%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        alignItems: "stretch",
        background: "var(--max-color-bg-secondary, #f3f4f6)",
      }}
    >
      <MiniAppHeader
        title={config?.title}
        subtitle={config?.subtitle}
        logoUrl={config?.logo_url}
        themeColor={themeColor}
        logoIconKey={config?.contacts?.mis_logo_icon}
      />
      {config?.site_kind === "mis" && misSession?.role ? (
        <div
          style={{
            flexShrink: 0,
            padding: "8px 16px",
            fontSize: 13,
            lineHeight: 1.4,
            color: "#0369a1",
            background: "#f0f9ff",
            borderBottom: "1px solid #bae6fd",
          }}
        >
          МИС:{" "}
          {misSession.role === "doctor"
            ? "врач (chat_id совпал с профилем врача)"
            : misSession.role === "patient"
              ? `пациент${misPatientToken ? " — доступ к карте по chat_id" : ""}`
              : "гость (привяжите chat_id в карте пациента или в профиле врача)"}
        </div>
      ) : null}
      <div
        className="miniapp-main-scroll"
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          overflowX: "hidden",
          overscrollBehavior: "contain",
          WebkitOverflowScrolling: "touch",
          paddingBottom: MINIAPP_TABBAR_SCROLL_PAD,
          scrollPaddingBottom: MINIAPP_TABBAR_SCROLL_PAD,
          /* Явный светлый фон: в dark-схеме MAX UI иначе тело страницы может быть невидимо */
          background: "#ffffff",
          color: "#111827",
        }}
      >
        {activeSlug === "__staff__" ? (
          <MiniAppStaffPanel token={miniToken} />
        ) : pages.length === 0 ? (
          <Flex
            direction="column"
            align="center"
            gap={8}
            style={{ padding: 32, textAlign: "center" }}
          >
            <Typography.Title>Пока нет опубликованных страниц</Typography.Title>
            <Typography.Body>
              Администратор ещё не наполнил сайт. Попробуйте позже.
            </Typography.Body>
          </Flex>
        ) : (
          <MiniAppPageContent
            page={activePage}
            organizationId={config?.organization_id}
            miniToken={miniToken}
            misRole={misSession?.role ?? null}
            themeColor={themeColor}
          />
        )}
      </div>
      <MiniAppTabbar
        items={navItemsWithStaff}
        activeSlug={activeSlug === "__staff__" ? "__staff__" : activePage?.slug || null}
        onChange={setActiveSlug}
        themeColor={themeColor}
      />
    </div>
  );
}
