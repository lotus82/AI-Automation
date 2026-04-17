import axios from "axios";
import { getPatientToken } from "../utils/patientMisAuth.js";
import { getBrowserIanaTimeZone } from "../utils/clientTimeZone.js";

/** Запросы МИС пациента: без токена портала; Bearer — только JWT ``mis_patient`` для /patient-session. */
const patientMisClient = axios.create({
  baseURL: "/api",
});

patientMisClient.interceptors.request.use((config) => {
  const url = String(config.url || "");
  if (url.includes("/mis/patient-session")) {
    const t = getPatientToken();
    if (t) {
      config.headers.Authorization = `Bearer ${t}`;
    }
  }
  const tz = getBrowserIanaTimeZone();
  if (tz) {
    config.headers["X-Client-Timezone"] = tz;
  }
  return config;
});

patientMisClient.interceptors.response.use(
  (r) => r,
  (error) => Promise.reject(error),
);

export default patientMisClient;
