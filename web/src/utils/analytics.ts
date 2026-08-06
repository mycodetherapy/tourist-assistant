/** Яндекс Метрика — лендинг и воронка регистрации (progulyai.ru). */

import { hasAnalyticsConsent } from "./cookieConsent";

export const METRIKA_GOALS = {
  LANDING_VIEW: "landing_view",
  CTA_TRY_CLICK: "cta_try_click",
  CTA_REGISTER_CLICK: "cta_register_click",
  CTA_LOGIN_CLICK: "cta_login_click",
  TRY_PAGE_VIEW: "try_page_view",
  TRY_TRIP_CREATED: "try_trip_created",
  TRY_BUILD_SUCCESS: "try_build_success",
  GUEST_REGISTER_GATE: "guest_register_gate",
  GUEST_REGISTER_CLICK: "guest_register_click",
  REGISTER_PAGE_VIEW: "register_page_view",
  REGISTER_SUCCESS: "register_success",
  PROXYAPI_LINK_CLICK: "proxyapi_link_click",
} as const;

export type MetrikaGoal = (typeof METRIKA_GOALS)[keyof typeof METRIKA_GOALS];

type YmStub = ((...args: unknown[]) => void) & { a?: unknown[][]; l?: number };

declare global {
  interface Window {
    ym?: YmStub;
  }
}

function getCounterId(): number | null {
  const raw = import.meta.env.VITE_YANDEX_METRIKA_ID?.trim();
  if (!raw) return null;
  const id = Number.parseInt(raw, 10);
  return Number.isFinite(id) && id > 0 ? id : null;
}

let initialized = false;

export function isMetrikaEnabled(): boolean {
  return getCounterId() !== null;
}

/** Подключить счётчик только после согласия на аналитику (no-op без ID / без согласия). */
export function initYandexMetrika(): void {
  const counterId = getCounterId();
  if (!counterId || initialized || typeof window === "undefined") return;
  if (!hasAnalyticsConsent()) return;
  initialized = true;

  window.ym =
    window.ym ||
    function (...args: unknown[]) {
      (window.ym!.a = window.ym!.a || []).push(args);
    };
  window.ym.l = Date.now();

  const script = document.createElement("script");
  script.async = true;
  script.src = "https://mc.yandex.ru/metrika/tag.js";
  document.head.appendChild(script);

  window.ym(counterId, "init", {
    defer: true,
    clickmap: true,
    trackLinks: true,
    accurateTrackBounce: true,
    webvisor: true,
  });
}

export function reachGoal(goal: MetrikaGoal, params?: Record<string, unknown>): void {
  const counterId = getCounterId();
  if (!counterId || !hasAnalyticsConsent() || typeof window.ym !== "function") return;
  if (params && Object.keys(params).length > 0) {
    window.ym(counterId, "reachGoal", goal, params);
  } else {
    window.ym(counterId, "reachGoal", goal);
  }
}

/** Виртуальный просмотр страницы (SPA). */
export function hitPage(path: string, title?: string): void {
  const counterId = getCounterId();
  if (!counterId || !hasAnalyticsConsent() || typeof window.ym !== "function") return;
  window.ym(counterId, "hit", path, title ? { title } : undefined);
}
