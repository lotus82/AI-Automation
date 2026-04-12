import { Navigate, useLocation } from "react-router-dom";

/** Сохраняет query string при редиректе (например ?tab=bots). */
export function RedirectWithSearch({ to }) {
  const { search } = useLocation();
  return <Navigate to={`${to}${search}`} replace />;
}
