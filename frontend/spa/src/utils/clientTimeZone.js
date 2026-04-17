/** IANA TZ браузера (Europe/Moscow и т.д.) для заголовка X-Client-Timezone. */
export function getBrowserIanaTimeZone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  } catch {
    return "";
  }
}
