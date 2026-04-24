import { Navigate } from "react-router-dom";
import { PAGE_H1, PAGE_TEXT } from "../styles/pageLayout.js";

/** Раздел перенесён в Интеграции → «Телефония». Старый URL сохраняем для закладок. */
export function TesterPage() {
  return <Navigate to="/integrations?section=telephony" replace />;
}
