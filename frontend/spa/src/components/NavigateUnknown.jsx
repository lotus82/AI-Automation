import { Navigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore.js";

/** Неизвестный путь: гость → «/», с токеном → QA (стоит после явных маршрутов, «/» не перехватывает). */
export function NavigateUnknown() {
  const token = useAuthStore((s) => s.token);
  return <Navigate to={token ? "/scenarios/qa-analytics" : "/"} replace />;
}
