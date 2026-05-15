import { Flex } from "@maxhub/max-ui";
import { useEffect, useMemo, useState } from "react";
import { siteLogoImgSrc } from "../../utils/siteLogoUrl.js";
import { isValidMisLogoIconKey, MisLogoIcon } from "../../utils/misMedicalBranding.jsx";

/** Шапка Mini App: логотип, название, подзаголовок, фон из theme_color. */
export function MiniAppHeader({ title, subtitle, logoUrl, themeColor, logoIconKey }) {
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

  return (
    <header
      style={{
        flexShrink: 0,
        flexGrow: 0,
        boxSizing: "border-box",
        paddingTop: "calc(env(safe-area-inset-top, 0px) + 16px)",
        paddingLeft: "max(16px, env(safe-area-inset-left, 0px))",
        paddingRight: "max(16px, env(safe-area-inset-right, 0px))",
        paddingBottom: 16,
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
