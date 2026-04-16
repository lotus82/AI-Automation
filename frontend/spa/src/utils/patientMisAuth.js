/** Локальное хранилище JWT пациента МИС (MAX / личный кабинет). */

const TOKEN_KEY = "mis_patient_jwt";
const PATIENT_ID_KEY = "mis_patient_id";
const ORG_ID_KEY = "mis_patient_org_id";

export function getPatientToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function setPatientSession(token, patientId, organizationId) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
    if (patientId) localStorage.setItem(PATIENT_ID_KEY, String(patientId));
    else localStorage.removeItem(PATIENT_ID_KEY);
    if (organizationId) localStorage.setItem(ORG_ID_KEY, String(organizationId));
    else localStorage.removeItem(ORG_ID_KEY);
  } catch {
    /* ignore */
  }
}

export function getStoredPatientId() {
  try {
    return localStorage.getItem(PATIENT_ID_KEY) || "";
  } catch {
    return "";
  }
}

export function getStoredOrganizationId() {
  try {
    return localStorage.getItem(ORG_ID_KEY) || "";
  } catch {
    return "";
  }
}

export function clearPatientSession() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PATIENT_ID_KEY);
    localStorage.removeItem(ORG_ID_KEY);
  } catch {
    /* ignore */
  }
}

export function parseOrganizationIdFromStartParam(startParam) {
  const m = String(startParam || "").match(/^reg_org_([0-9a-fA-F-]{36})_doc_/i);
  return m ? m[1] : null;
}
