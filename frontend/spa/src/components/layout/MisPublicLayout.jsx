import { Activity } from "lucide-react";
import { Outlet, useLocation } from "react-router-dom";

/**
 * Лёгкий каркас публичной зоны МИС (без сайдбара портала). Светлая медицинская палитра, адаптация под смартфон.
 */
export function MisPublicLayout() {
  const location = useLocation();
  const compact = location.pathname.startsWith("/public/mis/patient");

  return (
    <div className="min-h-dvh bg-[#f4f8fb] text-slate-800 antialiased">
      <header
        className={`border-b border-slate-200/80 bg-white/95 backdrop-blur-sm ${compact ? "shadow-sm" : "shadow-sm"}`}
      >
        <div
          className={`mx-auto flex max-w-2xl items-center gap-3 px-3 sm:px-4 ${compact ? "py-2.5" : "py-3"}`}
          style={{ paddingTop: `max(${compact ? "0.625rem" : "0.75rem"}, env(safe-area-inset-top, 0px))` }}
        >
          <div
            className={`flex shrink-0 items-center justify-center rounded-xl bg-teal-600 text-white shadow-md shadow-teal-600/20 ${compact ? "h-9 w-9" : "h-10 w-10"}`}
          >
            <Activity className={compact ? "h-4 w-4" : "h-5 w-5"} strokeWidth={2} aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            {compact ? (
              <>
                <div className="truncate text-[11px] font-semibold uppercase tracking-wide text-teal-700">
                  МИС
                </div>
                <div className="truncate text-sm font-medium text-slate-800">Портал пациента</div>
              </>
            ) : (
              <>
                <div className="text-xs font-semibold uppercase tracking-wide text-teal-700">
                  Медицинская информационная система
                </div>
                <div className="text-sm font-medium text-slate-700">Портал пациента</div>
              </>
            )}
          </div>
        </div>
      </header>
      <main
        className={`mx-auto max-w-2xl px-3 sm:px-4 ${compact ? "py-4 pb-8" : "py-6 pb-12"}`}
        style={{ paddingBottom: `max(${compact ? "2rem" : "3rem"}, env(safe-area-inset-bottom, 0px))` }}
      >
        <Outlet />
      </main>
    </div>
  );
}
