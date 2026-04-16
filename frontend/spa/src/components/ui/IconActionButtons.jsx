import { Link } from "react-router-dom";
import { Loader2, Pencil, Power, Trash2 } from "lucide-react";

const base =
  "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border transition-colors " +
  "focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60 " +
  "disabled:pointer-events-none disabled:opacity-40";

/** Редактировать (только иконка). */
export function IconEditButton({ title = "Редактировать", className = "", ...rest }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      className={`${base} border-slate-600 text-slate-200 hover:bg-slate-800 ${className}`}
      {...rest}
    >
      <Pencil className="h-4 w-4" strokeWidth={2} aria-hidden />
    </button>
  );
}

/** Как IconEditButton, но ссылка (например в список редактирования). */
export function IconEditLink({ to, title = "Редактировать", className = "", ...rest }) {
  return (
    <Link
      to={to}
      title={title}
      aria-label={title}
      className={`${base} border-slate-600 text-slate-200 hover:bg-slate-800 ${className}`}
      {...rest}
    >
      <Pencil className="h-4 w-4" strokeWidth={2} aria-hidden />
    </Link>
  );
}

/** Удалить (только иконка). При busy показывается индикатор загрузки. */
export function IconDeleteButton({ title = "Удалить", busy = false, className = "", ...rest }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      className={`${base} border-red-900/60 text-red-300 hover:bg-red-950/40 ${className}`}
      {...rest}
    >
      {busy ? (
        <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} aria-hidden />
      ) : (
        <Trash2 className="h-4 w-4" strokeWidth={2} aria-hidden />
      )}
    </button>
  );
}

/** Вкл/выкл организации (супер-админ): активная — акцент, неактивная — приглушённо. */
export function IconOrganizationActiveToggle({ isActive, title, className = "", ...rest }) {
  const defaultTitle = isActive ? "Отключить организацию" : "Включить организацию";
  const t = title ?? defaultTitle;
  return (
    <button
      type="button"
      title={t}
      aria-label={t}
      className={`${base} ${
        isActive
          ? "border-emerald-700/50 text-emerald-300 hover:bg-emerald-950/35"
          : "border-slate-600 text-slate-400 hover:bg-slate-800"
      } ${className}`}
      {...rest}
    >
      <Power className="h-4 w-4" strokeWidth={2} aria-hidden />
    </button>
  );
}
