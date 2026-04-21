/** Спец-страницы МИС Mini App и фильтрация меню по роли / целевой аудитории конструктора. */

export const MIS_DOCTOR_PAGE_KINDS = ["mis_patients", "mis_doctor_card"];

export const MIS_PATIENT_PAGE_KINDS = [
  "mis_patient_card",
  "mis_patient_profile",
  "mis_patient_diary",
  "mis_patient_tips",
];

/**
 * @param {Record<string, unknown> | null | undefined} contacts
 * @returns {"doctor" | "patient"}
 */
export function getMisMiniappAudience(contacts) {
  const v = contacts && contacts.mis_miniapp_audience;
  if (String(v || "").toLowerCase() === "patient") return "patient";
  return "doctor";
}

/**
 * Показывать ли страницу в нижнем меню Mini App МИС.
 * @param {{ page_kind?: string, mis_audience?: string | null }} page
 * @param {"doctor" | "patient"} audience — legacy: из contacts (если у страницы нет mis_audience)
 * @param {string | null | undefined} misRole — doctor | patient | guest из /mis/session
 */
export function misSitePageVisibleInNav(page, audience, misRole) {
  const ma = String(page?.mis_audience || "").toLowerCase();
  if (ma === "doctor" || ma === "patient") {
    if (!misRole || misRole === "guest") return false;
    return misRole === ma;
  }
  const pk = String(page?.page_kind || "content").toLowerCase();
  if (audience === "patient") {
    if (!MIS_PATIENT_PAGE_KINDS.includes(pk)) return false;
    return misRole === "patient";
  }
  if (!MIS_DOCTOR_PAGE_KINDS.includes(pk)) return false;
  return misRole === "doctor";
}

/**
 * Для сайтов без site_kind=mis: скрыть только список врача у не-врачей.
 */
export function legacyMisPatientsSlugAllowed(page, misRole) {
  const pk = String(page?.page_kind || "content").toLowerCase();
  if (pk !== "mis_patients") return true;
  return misRole === "doctor";
}
