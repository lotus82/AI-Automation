import {
  Book,
  BookOpen,
  Building2,
  Calendar,
  CalendarDays,
  ClipboardList,
  FileText,
  Globe,
  Layers,
  LayoutGrid,
  Plug,
  ScrollText,
  Settings,
  Stethoscope,
  Store,
  UserCog,
  UsersRound,
  X,
} from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuthStore } from "../../store/authStore.js";
import { OrganizationScopeSelect } from "./OrganizationScopeSelect.jsx";

const linkClass = ({ isActive }) =>
  [
    "flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors",
    isActive
      ? "bg-emerald-600/20 text-emerald-300"
      : "text-slate-300 hover:bg-slate-800 hover:text-white",
  ].join(" ");

const SCENARIO_SECTIONS = ["qa-analytics", "ai-trainer", "leadgen"];

const BASE_NAV = [
  {
    to: "/scenarios/qa-analytics",
    label: "Сценарии",
    icon: Layers,
    scenariosGroup: true,
  },
  { to: "/roles", section: "roles", label: "Роли", icon: UsersRound },
  { to: "/knowledge", section: "knowledge", label: "База знаний", icon: Book },
  { to: "/questionnaires", section: "questionnaires", label: "Опросники", icon: ClipboardList },
  { to: "/forms", section: "forms", label: "Мероприятия", icon: FileText },
  { to: "/bookings", section: "bookings", label: "Записи", icon: CalendarDays },
  { to: "/schedule", section: "schedule", label: "Расписания", icon: Calendar },
  { to: "/applications", section: "applications", label: "Приложения", icon: LayoutGrid, managerOnly: true },
  { to: "/sites", section: "sites", label: "Сайты", icon: Globe, managerOnly: true },
  { to: "/shops", section: "shops", label: "Магазины", icon: Store },
  { to: "/mis", section: "mis", label: "МИС", icon: Stethoscope },
  { to: "/documents", section: "documents", label: "Читатель", icon: BookOpen, managerOnly: true },
  { to: "/settings", section: "settings", label: "Настройки", icon: Settings },
  { to: "/integrations", section: "integrations", label: "Интеграции", icon: Plug },
  { to: "/logs", section: "logs", label: "Логи", icon: ScrollText },
  
];

function SidebarContent({ onNavigate, headerAction }) {
  const { pathname } = useLocation();
  const user = useAuthStore((s) => s.user);
  const sections = new Set(user?.sections || []);

  const showItem = (item) => {
    if (!user) return false;
    if (item.scenariosGroup) {
      if (user.role === "super_admin" || user.role === "org_admin") return true;
      return SCENARIO_SECTIONS.some((s) => sections.has(s));
    }
    if (item.managerOnly) {
      return (
        user.role === "super_admin" ||
        user.role === "org_admin" ||
        user.role === "director"
      );
    }
    if (user.role === "super_admin" || user.role === "org_admin") return true;
    return sections.has(item.section);
  };

  const mainItems = BASE_NAV.filter(showItem);

  return (
    <>
      <div className="border-b border-slate-800 px-4 py-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-wide text-slate-500">Lotus AI</div>
            <div className="text-lg font-semibold text-white">Панель</div>
          </div>
          {headerAction ? <div className="shrink-0 pt-0.5">{headerAction}</div> : null}
        </div>
      </div>
      <nav
        className="flex flex-1 flex-col gap-1 overflow-y-auto p-3"
        aria-label="Основная навигация"
      >
        {user?.role === "super_admin" ? (
          <NavLink to="/portal/organizations" className={linkClass} onClick={() => onNavigate?.()}>
            <Building2 className="mr-2 h-4 w-4 shrink-0 opacity-90" strokeWidth={1.75} aria-hidden />
            Организации
          </NavLink>
        ) : null}
        <OrganizationScopeSelect />
        {(user?.role === "org_admin" || user?.role === "director") && (
          <NavLink to="/portal/users" className={linkClass} onClick={() => onNavigate?.()}>
            <UserCog className="mr-2 h-4 w-4 shrink-0 opacity-90" strokeWidth={1.75} aria-hidden />
            Пользователи
          </NavLink>
        )}
        {mainItems.map((item) => {
          const { to, label, icon: Icon, scenariosGroup, end } = item;
          const scenariosActive = Boolean(scenariosGroup && pathname.startsWith("/scenarios"));
          const misActive = Boolean(item.section === "mis" && pathname.startsWith("/mis"));
          const documentsActive = Boolean(item.section === "documents" && pathname.startsWith("/documents"));
          return (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                linkClass({ isActive: isActive || scenariosActive || misActive || documentsActive })
              }
              end={Boolean(end) && !scenariosGroup}
              onClick={() => onNavigate?.()}
            >
              <Icon className="mr-2 h-4 w-4 shrink-0 opacity-90" strokeWidth={1.75} aria-hidden />
              {label}
            </NavLink>
          );
        })}
      </nav>
    </>
  );
}

/** Боковая колонка на экранах md и шире. */
export function Sidebar() {
  return (
    <aside className="hidden w-56 shrink-0 flex-col border-r border-slate-800 bg-slate-900/80 md:flex">
      <SidebarContent />
    </aside>
  );
}

/** Выезжающее меню на узких экранах. */
export function SidebarMobileDrawer({ open, onClose }) {
  if (!open) return null;

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-40 bg-black/60 md:hidden"
        aria-label="Закрыть меню"
        onClick={onClose}
      />
      <aside
        id="mobile-nav-drawer"
        className="fixed inset-y-0 left-0 z-50 flex w-[min(20rem,calc(100vw-2rem))] max-w-[min(100vw-2rem,20rem)] flex-col border-r border-slate-800 bg-slate-900 shadow-2xl md:hidden"
        role="dialog"
        aria-modal="true"
        aria-label="Навигация по разделам"
      >
        <SidebarContent
          onNavigate={onClose}
          headerAction={
            <button
              type="button"
              className="rounded-lg border border-slate-600 p-1.5 text-slate-300 hover:bg-slate-800 hover:text-white"
              aria-label="Закрыть меню"
              onClick={onClose}
            >
              <X className="h-4 w-4" strokeWidth={2} aria-hidden />
            </button>
          }
        />
      </aside>
    </>
  );
}
