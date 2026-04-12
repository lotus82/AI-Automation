import { Navigate, useLocation } from "react-router-dom";

/**
 * Точка входа для встраивания в Битрикс24: переносит в раздел «Сценарии»,
 * сохраняя query-параметры iframe (DOMAIN, APP_SID, AUTH_ID и т.д.).
 * Укажите в настройках приложения Битрикс24 путь:
 * `https://<ваш-хост>/bitrix` или сразу `https://<ваш-хост>/scenarios/qa-analytics`.
 */
export function BitrixScenariosRedirect() {
  const { search } = useLocation();
  return <Navigate to={`/scenarios/qa-analytics${search}`} replace />;
}
