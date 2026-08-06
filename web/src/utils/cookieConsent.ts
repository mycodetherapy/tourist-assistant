/** Согласие на cookies / Яндекс.Метрику (localStorage). */

export const COOKIE_CONSENT_KEY = "progulyai_cookie_consent";
export const COOKIE_CONSENT_EVENT = "progulyai:cookie-consent";

export type CookieConsentValue = "accepted" | "necessary";

export function getCookieConsent(): CookieConsentValue | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(COOKIE_CONSENT_KEY);
  if (raw === "accepted" || raw === "necessary") return raw;
  return null;
}

export function setCookieConsent(value: CookieConsentValue): void {
  localStorage.setItem(COOKIE_CONSENT_KEY, value);
  window.dispatchEvent(new CustomEvent(COOKIE_CONSENT_EVENT, { detail: value }));
}

export function hasAnalyticsConsent(): boolean {
  return getCookieConsent() === "accepted";
}
