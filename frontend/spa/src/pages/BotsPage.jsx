import { Navigate } from "react-router-dom";
import { PAGE_H1, PAGE_TEXT } from "../styles/pageLayout.js";

/** Раздел перенесён в QA-аналитика → вкладка «Боты». Старый URL сохраняем для закладок. */
export function BotsPage() {
  return <Navigate to="/scenarios/qa-analytics?tab=bots" replace />;
}
