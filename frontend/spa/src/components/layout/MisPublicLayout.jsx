import { Activity } from "lucide-react";
import { Outlet } from "react-router-dom";

/**
 * Лёгкий каркас публичной зоны МИС (без сайдбара портала). Светлая медицинская палитра.
 */
export function MisPublicLayout() {
  return (
    <div className="min-h-dvh bg-[#f4f8fb] text-slate-800 antialiased">
      <header className="border-b border-slate-200/80 bg-white/95 shadow-sm backdrop-blur-sm">
        <div
          className="mx-auto flex max-w-2xl items-center gap-3 px-4 py-3"
          style={{ paddingTop: "max(0.75rem, env(safe-area-inset-top, 0px))" }}
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-600 text-white shadow-md shadow-teal-600/20">
            <Activity className="h-5 w-5" strokeWidth={2} aria-hidden />
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-teal-700">Медицинская информационная система</div>
            <div className="text-sm font-medium text-slate-700">Портал пациента</div>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-2xl px-4 py-6 pb-12">
        <Outlet />
      </main>
    </div>
  );
}
