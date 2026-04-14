import {
  Book,
  Building2,
  Calendar,
  ClipboardList,
  FileText,
  Layers,
  Plug,
  ScrollText,
  Settings,
  ShoppingBag,
  UserCog,
  UsersRound,
} from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuthStore } from "../../store/authStore.js";

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
  { to: "/questionnaires", section: "questionnaires", label: "Опросники", icon: ClipboardList },
  { to: "/forms", section: "forms", label: "Формы", icon: FileText },
  { to: "/shops", section: "shops", label: "Магазины", icon: ShoppingBag },
  { to: "/integrations", section: "integrations", label: "Интеграции", icon: Plug },
  { to: "/roles", section: "roles", label: "Роли", icon: UsersRound },
  { to: "/settings", section: "settings", label: "Настройки", icon: Settings },
  { to: "/logs", section: "logs", label: "Логи", icon: ScrollText },
  { to: "/knowledge", section: "knowledge", label: "База знаний", icon: Book },
  { to: "/schedule", section: "schedule", label: "Расписание", icon: Calendar },
];

export function Sidebar() {
  const { pathname } = useLocation();
  const user = useAuthStore((s) => s.user);
  const sections = new Set(user?.sections || []);

  const showItem = (item) => {
    if (!user) return false;
    if (item.scenariosGroup) {
      if (user.role === "super_admin" || user.role === "org_admin") return true;
      return SCENARIO_SECTIONS.some((s) => sections.has(s));
    }
    if (user.role === "super_admin" || user.role === "org_admin") return true;
    return sections.has(item.section);
  };

  const mainItems = BASE_NAV.filter(showItem);

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-slate-800 bg-slate-900/80">
      <div className="border-b border-slate-800 px-4 py-4">
        <div className="text-xs uppercase tracking-wide text-slate-500">Sales AI</div>
        <div className="text-lg font-semibold text-white">Панель</div>
      </div>
      <nav
        className="flex flex-1 flex-col gap-1 overflow-y-auto p-3"
        aria-label="Основная навигация"
      >
        {user?.role === "super_admin" ? (
          <NavLink to="/portal/organizations" className={linkClass}>
            <Building2 className="mr-2 h-4 w-4 shrink-0 opacity-90" strokeWidth={1.75} aria-hidden />
            Организации
          </NavLink>
        ) : null}
        {(user?.role === "org_admin" || user?.role === "director") && (
          <NavLink to="/portal/users" className={linkClass}>
            <UserCog className="mr-2 h-4 w-4 shrink-0 opacity-90" strokeWidth={1.75} aria-hidden />
            Пользователи
          </NavLink>
        )}
        {mainItems.map((item) => {
          const { to, label, icon: Icon, scenariosGroup, end } = item;
          const scenariosActive = Boolean(scenariosGroup && pathname.startsWith("/scenarios"));
          return (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                linkClass({ isActive: isActive || scenariosActive })
              }
              end={Boolean(end) && !scenariosGroup}
            >
              <Icon className="mr-2 h-4 w-4 shrink-0 opacity-90" strokeWidth={1.75} aria-hidden />
              {label}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
