import { Calendar } from "lucide-react";
import { useMemo, useRef } from "react";
import { formatRuDottedBirthInput, isoYmdToRuDotted, parseRuDottedToIsoYmd } from "../../utils/dateTimeFormat.js";

const defaultInputStyle = {
  flex: 1,
  maxWidth: "none",
  padding: "10px 12px",
  fontSize: 16,
  borderRadius: 8,
  border: "1px solid #e5e7eb",
  color: "#111827",
  background: "#fff",
  boxSizing: "border-box",
};

/**
 * Дата рождения: текст ДД.ММ.ГГГГ + кнопка календаря (type=date), значения синхронизированы.
 * @param {string} value — дата в формате ДД.ММ.ГГГГ
 * @param {(next: string) => void} onChange
 */
export function BirthDateRuField({
  value,
  onChange,
  accent = "#2563eb",
  disabled = false,
  inputStyle,
  hint,
}) {
  const dateInputRef = useRef(null);
  const accentColor = (accent || "#2563eb").trim() || "#2563eb";
  const hiddenDateValue = parseRuDottedToIsoYmd(value) || "";
  const todayIsoMax = useMemo(() => new Date().toISOString().slice(0, 10), []);

  const openDatePicker = () => {
    if (disabled) return;
    const el = dateInputRef.current;
    if (!el) return;
    if (typeof el.showPicker === "function") {
      try {
        el.showPicker();
        return;
      } catch {
        /* ignore */
      }
    }
    el.click();
  };

  const onBirthTextChange = (v) => {
    onChange(formatRuDottedBirthInput(v));
  };

  const onPickerChange = (e) => {
    const v = e.target.value;
    onChange(v ? isoYmdToRuDotted(v) : "");
  };

  return (
    <div>
      <div style={{ display: "flex", width: "100%", alignItems: "stretch", gap: 8 }}>
        <input
          type="text"
          inputMode="numeric"
          placeholder="ДД.ММ.ГГГГ"
          value={value}
          onChange={(e) => onBirthTextChange(e.target.value)}
          disabled={disabled}
          aria-label="Дата рождения (ДД.ММ.ГГГГ)"
          style={{ ...defaultInputStyle, ...inputStyle }}
        />
        <input
          ref={dateInputRef}
          type="date"
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          value={hiddenDateValue}
          onChange={onPickerChange}
          disabled={disabled}
          min="1900-01-01"
          max={todayIsoMax}
        />
        <button
          type="button"
          onClick={openDatePicker}
          disabled={disabled}
          title="Открыть календарь"
          aria-label="Открыть календарь"
          style={{
            flexShrink: 0,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: 44,
            minWidth: 44,
            height: 44,
            borderRadius: 8,
            border: `1px solid ${accentColor}`,
            background: disabled ? "#f3f4f6" : "rgba(255,255,255,0.95)",
            color: accentColor,
            cursor: disabled ? "not-allowed" : "pointer",
            opacity: disabled ? 0.6 : 1,
          }}
        >
          <Calendar className="h-5 w-5" strokeWidth={2} aria-hidden />
        </button>
      </div>
      {hint ? <p style={{ margin: "6px 0 0", fontSize: 12, color: "#6b7280" }}>{hint}</p> : null}
    </div>
  );
}
