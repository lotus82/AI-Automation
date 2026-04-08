import {
  BarChart3,
  Book,
  Calendar,
  ClipboardList,
  FileText,
  GraduationCap,
  Home,
  MessageSquare,
  Mic,
  Phone,
  Settings,
  TrendingUp,
} from "lucide-react";
import { NavLink } from "react-router-dom";

const linkClass = ({ isActive }) =>
  [
    "flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors",
    isActive
      ? "bg-emerald-600/20 text-emerald-300"
      : "text-slate-300 hover:bg-slate-800 hover:text-white",
  ].join(" ");

/** Единый список: дашборд, аналитика, модули — без дублей; переходы через NavLink (SPA). */
const navigation = [
  { to: "/", label: "Дашборд", icon: Home, end: true },
  { to: "/qa-analytics", label: "ИИ-контроль (QA)", icon: BarChart3 },
  { to: "/ai-trainer", label: "ИИ-тренер", icon: GraduationCap },
  { to: "/leadgen", label: "ИИ-лидогенератор", icon: TrendingUp },
  { to: "/tester", label: "Тестирование", icon: Mic },
  { to: "/questionnaires", label: "Опросники", icon: ClipboardList },
  { to: "/scenarios", label: "Сценарии", icon: FileText },
  { to: "/telephony", label: "Телефония", icon: Phone },
  { to: "/settings", label: "Настройки", icon: Settings },
  { to: "/knowledge", label: "База знаний", icon: Book },
  { to: "/bots", label: "Боты", icon: MessageSquare },
  { to: "/schedule", label: "Расписание", icon: Calendar },
];

export function Sidebar() {
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
        {navigation.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} className={linkClass} end={Boolean(end)}>
            <Icon className="mr-2 h-4 w-4 shrink-0 opacity-90" strokeWidth={1.75} aria-hidden />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
