import { Navigate } from "react-router-dom";

/** Раздел перенесён в Интеграции → «Телефония». Старый URL сохраняем для закладок. */
export function TesterPage() {
  return <Navigate to="/integrations?section=telephony" replace />;
}
