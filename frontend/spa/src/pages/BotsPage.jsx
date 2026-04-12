import { Navigate } from "react-router-dom";

/** Раздел перенесён в QA-аналитика → вкладка «Боты». Старый URL сохраняем для закладок. */
export function BotsPage() {
  return <Navigate to="/scenarios/qa-analytics?tab=bots" replace />;
}
