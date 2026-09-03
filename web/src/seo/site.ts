import { APP_NAME, APP_TAGLINE } from "../brand";

export const SITE_ORIGIN = "https://progulyai.ru";

export const HOME_TITLE = `${APP_NAME} (progulyai.ru) — ${APP_TAGLINE}`;
export const HOME_DESCRIPTION =
  "Прогуляй (progulyai.ru) — сервис пеших маршрутов по городу: три варианта прогулки A/B/C с картой и ссылкой на Яндекс.Карты.";

export type SeoRobots = "index, follow" | "noindex, follow" | "noindex, nofollow";

export interface PageSeo {
  title: string;
  description: string;
  canonicalPath: string;
  robots: SeoRobots;
}

const PUBLIC_PAGES: Record<string, PageSeo> = {
  "/": {
    title: HOME_TITLE,
    description: HOME_DESCRIPTION,
    canonicalPath: "/",
    robots: "index, follow",
  },
  "/try": {
    title: `${APP_NAME} — собрать пеший маршрут без регистрации`,
    description:
      "Соберите три пеших маршрута A/B/C по городу без аккаунта: карта, остановки и ссылка в Яндекс.Карты. Одна сборка и один пересбор в пробном режиме.",
    canonicalPath: "/try",
    robots: "index, follow",
  },
  "/terms": {
    title: `Пользовательское соглашение — ${APP_NAME}`,
    description: `Пользовательское соглашение сервиса ${APP_NAME} (progulyai.ru): правила использования пеших маршрутов.`,
    canonicalPath: "/terms",
    robots: "index, follow",
  },
  "/privacy": {
    title: `Политика конфиденциальности — ${APP_NAME}`,
    description: `Политика конфиденциальности ${APP_NAME} (progulyai.ru): персональные данные, cookie и Яндекс.Метрика.`,
    canonicalPath: "/privacy",
    robots: "index, follow",
  },
};

const PRIVATE_PAGE: PageSeo = {
  title: APP_NAME,
  description: HOME_DESCRIPTION,
  canonicalPath: "/",
  robots: "noindex, nofollow",
};

export function canonicalUrl(path: string): string {
  if (path === "/") return `${SITE_ORIGIN}/`;
  return `${SITE_ORIGIN}${path}`;
}

export function resolvePageSeo(pathname: string): PageSeo {
  const path = pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
  return PUBLIC_PAGES[path] ?? { ...PRIVATE_PAGE, canonicalPath: path.startsWith("/") ? path : `/${path}` };
}

