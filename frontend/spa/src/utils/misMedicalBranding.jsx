import {
  Activity,
  Bandage,
  Cross,
  Heart,
  HeartPulse,
  Hospital,
  Microscope,
  Pill,
  Stethoscope,
  Syringe,
} from "lucide-react";

/** Допустимые ключи иконки логотипа МИС (хранится в contacts.mis_logo_icon). */
export const MIS_LOGO_ICON_MAP = {
  stethoscope: Stethoscope,
  heart_pulse: HeartPulse,
  heart: Heart,
  cross: Cross,
  activity: Activity,
  pill: Pill,
  bandage: Bandage,
  syringe: Syringe,
  microscope: Microscope,
  hospital: Hospital,
};

export const MIS_LOGO_ICON_OPTIONS = [
  { id: "stethoscope", label: "Стетоскоп" },
  { id: "heart_pulse", label: "Пульс" },
  { id: "heart", label: "Сердце" },
  { id: "cross", label: "Крест" },
  { id: "activity", label: "Кардио" },
  { id: "pill", label: "Таблетка" },
  { id: "bandage", label: "Пластырь" },
  { id: "syringe", label: "Шприц" },
  { id: "microscope", label: "Микроскоп" },
  { id: "hospital", label: "Клиника" },
];

export function isValidMisLogoIconKey(raw) {
  const s = typeof raw === "string" ? raw.trim() : "";
  return s && Object.prototype.hasOwnProperty.call(MIS_LOGO_ICON_MAP, s);
}

/**
 * Иконка логотипа МИС для шапки Mini App / превью.
 * @param {{ iconKey: string, size?: number, className?: string, strokeWidth?: number, style?: React.CSSProperties }} props
 */
export function MisLogoIcon({ iconKey, size = 24, className = "", strokeWidth = 1.75, style }) {
  const k = typeof iconKey === "string" ? iconKey.trim() : "";
  const Comp = MIS_LOGO_ICON_MAP[k];
  if (!Comp) return null;
  return <Comp className={className} size={size} strokeWidth={strokeWidth} style={style} aria-hidden />;
}

/** Типичная медицинская палитра (teal / blue / emerald — спокойные клинические оттенки). */
export const MEDICAL_THEME_COLOR_PRESETS = [
  { hex: "#0d9488", label: "Клинический teal" },
  { hex: "#0ea5e9", label: "Небесно-голубой" },
  { hex: "#0891b2", label: "Бирюзовый" },
  { hex: "#2563eb", label: "Синий" },
  { hex: "#1e40af", label: "Тёмно-синий" },
  { hex: "#1d4ed8", label: "Доверительный синий" },
  { hex: "#059669", label: "Зелёный (здоровье)" },
  { hex: "#047857", label: "Тёмный изумруд" },
  { hex: "#4338ca", label: "Индиго" },
  { hex: "#0369a1", label: "Глубокий голубой" },
  { hex: "#475569", label: "Нейтральный сланец" },
  { hex: "#0f766e", label: "Глубокий teal" },
];

/**
 * Ряд кнопок с пресетами цвета (для theme_color и акцента карты пациента).
 */
export function MedicalColorPresetRow({ value, onChange, className = "" }) {
  const normalized = typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value.trim()) ? value.trim().toLowerCase() : "";
  return (
    <div className={`flex flex-wrap gap-1.5 ${className}`} role="group" aria-label="Медицинская палитра">
      {MEDICAL_THEME_COLOR_PRESETS.map((p) => {
        const active = normalized === p.hex.toLowerCase();
        return (
          <button
            key={p.hex}
            type="button"
            title={p.label}
            onClick={() => onChange(p.hex)}
            className={[
              "h-8 w-8 shrink-0 rounded-full border-2 transition-transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-emerald-500/60",
              active ? "border-white ring-2 ring-emerald-400/80" : "border-slate-600 hover:border-slate-400",
            ].join(" ")}
            style={{ backgroundColor: p.hex }}
          />
        );
      })}
    </div>
  );
}
