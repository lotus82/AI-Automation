/** Совпадает с ``src.api.panel_settings_extras`` (бэкенд). */
export const PANEL_EXTRA_KIND = {
  NOTE: "note",
  TBANK_VK_STT: "tbank_voicekit_stt",
  TBANK_VK_TTS: "tbank_voicekit_tts",
};

export function isTbankVoiceKitRow(r) {
  if (!r || !r.kind) return false;
  return r.kind === PANEL_EXTRA_KIND.TBANK_VK_STT || r.kind === PANEL_EXTRA_KIND.TBANK_VK_TTS;
}
