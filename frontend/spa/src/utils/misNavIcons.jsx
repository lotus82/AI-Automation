import {
  Activity,
  BookOpen,
  BookMarked,
  Calendar,
  ClipboardList,
  FileText,
  Heart,
  HeartPulse,
  HelpCircle,
  Home,
  Hospital,
  MessageCircle,
  Pill,
  Settings,
  Stethoscope,
  User,
  Users,
} from "lucide-react";

/** Lucide-иконки для пунктов нижнего меню Mini App МИС (ключ в menu_items.nav_icon). */
export const MIS_NAV_ICON_MAP = {
  user: User,
  users: Users,
  clipboard_list: ClipboardList,
  book_open: BookOpen,
  book_marked: BookMarked,
  heart_pulse: HeartPulse,
  heart: Heart,
  stethoscope: Stethoscope,
  hospital: Hospital,
  pill: Pill,
  activity: Activity,
  calendar: Calendar,
  file_text: FileText,
  home: Home,
  settings: Settings,
  message: MessageCircle,
  help: HelpCircle,
};

export const MIS_NAV_ICON_OPTIONS = [
  { id: "", label: "Без иконки" },
  { id: "user", label: "Профиль (человек)" },
  { id: "clipboard_list", label: "Карточка / список" },
  { id: "book_open", label: "Дневник / книга" },
  { id: "book_marked", label: "Советы / закладка" },
  { id: "heart_pulse", label: "Пульс / здоровье" },
  { id: "stethoscope", label: "Врач" },
  { id: "users", label: "Пациенты" },
  { id: "calendar", label: "Календарь" },
  { id: "pill", label: "Лекарства" },
  { id: "hospital", label: "Клиника" },
  { id: "message", label: "Сообщения" },
  { id: "help", label: "Помощь" },
  { id: "settings", label: "Настройки" },
];

export function isValidMisNavIconKey(raw) {
  const s = typeof raw === "string" ? raw.trim() : "";
  return !s || Object.prototype.hasOwnProperty.call(MIS_NAV_ICON_MAP, s);
}

/** @param {{ iconKey: string, size?: number, className?: string, strokeWidth?: number, style?: object }} props */
export function MisNavIcon({ iconKey, size = 18, className = "", strokeWidth = 2, style }) {
  const k = typeof iconKey === "string" ? iconKey.trim() : "";
  const Comp = MIS_NAV_ICON_MAP[k];
  if (!Comp) return null;
  return <Comp className={className} size={size} strokeWidth={strokeWidth} style={style} aria-hidden />;
}
