import { NavLink, Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "../store/authStore.js";
import {
  PAGE_INNER,
  PAGE_TEXT,
  SCENARIOS_SUBSECTIONS,
  TAB_ROW,
  firstScenariosPathForUser,
  tabBtn,
} from "../styles/pageLayout.js";

export function ScenariosIndexRedirect() {
  const user = useAuthStore((s) => s.user);
  const sections = new Set(user?.sections || []);
  const next = firstScenariosPathForUser(user, sections);
  if (!next) {
    return <Navigate to="/questionnaires" replace />;
  }
  return <Navigate to={`/scenarios/${next}`} replace />;
}

export function ScenariosLayout() {
  const user = useAuthStore((s) => s.user);
  const sections = new Set(user?.sections || []);

  const visible = SCENARIOS_SUBSECTIONS.filter((item) => {
    if (!user) return false;
    if (user.role === "super_admin" || user.role === "org_admin") return true;
    return sections.has(item.section);
  });

  if (visible.length === 0) {
    return <Navigate to="/questionnaires" replace />;
  }

  return (
    <div className={`${PAGE_INNER} ${PAGE_TEXT}`}>
      <div className={TAB_ROW} role="tablist" aria-label="Сценарии">
        {visible.map((item) => (
          <NavLink
            key={item.path}
            to={`/scenarios/${item.path}`}
            end
            role="tab"
            className={({ isActive }) => tabBtn(isActive)}
          >
            {item.label}
          </NavLink>
        ))}
      </div>
      <div className="mt-0 w-full min-w-0">
        <Outlet />
      </div>
    </div>
  );
}
