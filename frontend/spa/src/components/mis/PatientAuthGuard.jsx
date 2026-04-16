import { useCallback, useEffect, useState } from "react";
import { Loader2, MessageCircle, Smartphone } from "lucide-react";
import patientMisClient from "../../api/patientMisClient.js";
import {
  clearPatientSession,
  getPatientToken,
  getStoredOrganizationId,
  getStoredPatientId,
  parseOrganizationIdFromStartParam,
  setPatientSession,
} from "../../utils/patientMisAuth.js";

const card =
  "rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm shadow-slate-200/50 sm:p-5";

function getMaxInitDataFromWindow() {
  if (typeof window === "undefined") return "";
  try {
    const w = window;
    const raw = w.WebApp?.initData ?? w.Telegram?.WebApp?.initData;
    return typeof raw === "string" ? raw.trim() : "";
  } catch {
    return "";
  }
}

function getMaxStartParamUnsafe() {
  if (typeof window === "undefined") return "";
  try {
    const u = window.WebApp?.initDataUnsafe ?? window.Telegram?.WebApp?.initDataUnsafe;
    const sp = u?.start_param ?? u?.startParam;
    return typeof sp === "string" ? sp.trim() : "";
  } catch {
    return "";
  }
}

/**
 * @param {{ legacyPublicPatientId?: string, children: import("react").ReactNode, onAuthenticated?: (patientId: string) => void, onRegistrationRequired?: (draft: { organizationId: string, maxUserId: string, startParam: string | null, initData: string }) => void }} props
 */
export function PatientAuthGuard({
  legacyPublicPatientId,
  children,
  onAuthenticated,
  onRegistrationRequired,
}) {
  const [phase, setPhase] = useState(() => (legacyPublicPatientId ? "legacy" : "checking"));
  const [authError, setAuthError] = useState("");
  const [phoneLoginOpen, setPhoneLoginOpen] = useState(false);

  const runInit = useCallback(
    async (initDataRaw, organizationId) => {
      const org = String(organizationId || "").trim();
      const raw = String(initDataRaw || "").trim();
      if (!org || !raw) return false;
      setAuthError("");
      try {
        const headers = {};
        if (raw.length > 1200) {
          headers["X-Max-Init-Data"] = raw;
        }
        const { data } = await patientMisClient.get("/mis/auth/max/init", {
          params: {
            organization_id: org,
            ...(raw.length <= 1200 ? { init_data: raw } : {}),
          },
          headers,
        });
        if (!data.need_registration && data.access_token && data.patient_id) {
          setPatientSession(data.access_token, data.patient_id, data.organization_id);
          onAuthenticated?.(String(data.patient_id));
          setPhase("authed");
          return true;
        }
        if (data.need_registration) {
          onRegistrationRequired?.({
            organizationId: String(data.organization_id),
            maxUserId: String(data.max_user_id || ""),
            startParam: data.start_param ?? null,
            initData: raw,
          });
          setPhase("register");
          return true;
        }
      } catch (e) {
        const det = e?.response?.data?.detail;
        const msg = Array.isArray(det)
          ? det.map((x) => x?.msg ?? x).join("; ")
          : typeof det === "string"
            ? det
            : e?.message || "Ошибка входа";
        setAuthError(String(msg));
        setPhase("unauthed");
      }
      return false;
    },
    [onAuthenticated, onRegistrationRequired],
  );

  useEffect(() => {
    if (legacyPublicPatientId) {
      setPhase("legacy");
      return;
    }

    const token = getPatientToken();
    const pid = getStoredPatientId();
    if (token && pid) {
      patientMisClient
        .get("/mis/patient-session/me")
        .then(() => {
          onAuthenticated?.(pid);
          setPhase("authed");
        })
        .catch(() => {
          clearPatientSession();
          setPhase("unauthed");
        });
      return;
    }

    const search = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
    const maxData =
      search?.get("max_data") ||
      search?.get("init_data") ||
      search?.get("WebAppData") ||
      "";
    const orgFromQuery = search?.get("organization_id") || "";
    const startFromQuery = search?.get("start_param") || "";

    const fromWindow = getMaxInitDataFromWindow();
    const startUnsafe = getMaxStartParamUnsafe();
    const initRaw = maxData || fromWindow;
    const orgFromStart =
      parseOrganizationIdFromStartParam(startFromQuery) ||
      parseOrganizationIdFromStartParam(startUnsafe) ||
      getStoredOrganizationId();
    const organizationId = orgFromQuery || orgFromStart;

    if (initRaw && organizationId) {
      setPhase("checking");
      void runInit(initRaw, organizationId);
      return;
    }

    if (initRaw && !organizationId) {
      setAuthError("Не указана организация (organization_id). Откройте ссылку из чата клиники.");
      setPhase("unauthed");
      return;
    }

    setPhase("unauthed");
  }, [legacyPublicPatientId, runInit, onAuthenticated]);

  if (phase === "legacy") {
    return children;
  }

  if (phase === "checking") {
    return (
      <div className={`${card} flex flex-col items-center justify-center gap-3 py-16 text-slate-600`}>
        <Loader2 className="h-8 w-8 animate-spin text-teal-600" aria-hidden />
        <p className="text-sm">Вход…</p>
      </div>
    );
  }

  if (phase === "authed" || phase === "register") {
    return children;
  }

  return (
    <div className="space-y-4">
      <div className={card}>
        <h1 className="text-base font-semibold text-slate-900">Личный кабинет пациента</h1>
        <p className="mt-2 text-sm text-slate-600">
          Войдите через мессенджер MAX или дождитесь входа по SMS (скоро).
        </p>
        {authError ? (
          <p className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{authError}</p>
        ) : null}
        <div className="mt-4 flex flex-col gap-3">
          <button
            type="button"
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white shadow-md shadow-teal-600/20 active:scale-[0.99]"
            onClick={() => {
              const hint =
                typeof window !== "undefined" && window.WebApp?.initData
                  ? "Данные MAX уже доступны — обновите страницу или откройте мини-приложение из чата бота."
                  : "Откройте это приложение внутри MAX (мини-приложение клиники). После запуска вход выполнится автоматически.";
              window.alert(hint);
            }}
          >
            <MessageCircle className="h-5 w-5 shrink-0" strokeWidth={2} aria-hidden />
            Войти через MAX
          </button>
          <button
            type="button"
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white py-3 text-sm font-semibold text-slate-800 active:bg-slate-50"
            onClick={() => setPhoneLoginOpen((v) => !v)}
          >
            <Smartphone className="h-5 w-5 shrink-0 text-slate-600" strokeWidth={2} aria-hidden />
            Войти по телефону
          </button>
        </div>
        {phoneLoginOpen ? (
          <div className="mt-4 rounded-xl border border-amber-100 bg-amber-50/80 px-3 py-3 text-sm text-amber-950">
            <p className="font-medium">Скоро</p>
            <p className="mt-1 text-amber-900/90">
              Вход по номеру телефона и коду из SMS будет доступен в следующей версии. Пока используйте MAX.
            </p>
          </div>
        ) : null}
      </div>
      <p className="px-1 text-center text-xs text-slate-500">
        Есть ссылка на карту от врача? Она откроется без входа в MAX.
      </p>
    </div>
  );
}
