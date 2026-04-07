import { useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useBitrixAuthStore } from "../store/bitrixAuthStore";

/**
 * Парсит параметры авторизации/встраивания из URL (типично для iframe Битрикс24).
 * Поддерживаются варианты: DOMAIN, APP_SID, AUTH_ID, PLACEMENT (регистр как в query).
 */
function parseBitrixQuery(searchParams) {
  const get = (keys) => {
    for (const k of keys) {
      const v = searchParams.get(k);
      if (v != null && String(v).trim() !== "") return String(v).trim();
    }
    return null;
  };

  const domain = get(["DOMAIN", "domain"]);
  const appSid = get(["APP_SID", "app_sid"]);

  const extra = {};
  searchParams.forEach((value, key) => {
    const lk = key.toLowerCase();
    if (["domain", "app_sid"].includes(lk)) return;
    extra[key] = value;
  });

  return { domain, appSid, extra };
}

/**
 * Синхронизирует URL → Zustand при монтировании и при смене query.
 * Вызывайте один раз в корне приложения (например в App.jsx).
 */
export function useBitrixAuth() {
  const [searchParams] = useSearchParams();
  const setFromParsed = useBitrixAuthStore((s) => s.setFromParsed);

  const parsed = useMemo(() => parseBitrixQuery(searchParams), [searchParams]);

  useEffect(() => {
    setFromParsed(parsed);
  }, [parsed, setFromParsed]);

  return {
    domain: parsed.domain,
    appSid: parsed.appSid,
    extra: parsed.extra,
    /** true, если хотя бы один «битриксовый» маркер есть в URL */
    isEmbedded: Boolean(parsed.domain || parsed.appSid),
  };
}
