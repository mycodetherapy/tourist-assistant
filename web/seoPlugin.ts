import type { Plugin } from "vite";

function escapeAttr(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

/** Опциональные meta верификации Яндекс.Вебмастера и Google Search Console. */
export function seoPlugin(): Plugin {
  let yandexVerification = "";
  let googleVerification = "";

  return {
    name: "progulyai-seo",
    configResolved(config) {
      yandexVerification = String(config.env.VITE_YANDEX_VERIFICATION ?? "").trim();
      googleVerification = String(config.env.VITE_GOOGLE_SITE_VERIFICATION ?? "").trim();
    },
    transformIndexHtml(html) {
      const extraMeta = [
        yandexVerification
          ? `    <meta name="yandex-verification" content="${escapeAttr(yandexVerification)}" />`
          : "",
        googleVerification
          ? `    <meta name="google-site-verification" content="${escapeAttr(googleVerification)}" />`
          : "",
      ]
        .filter(Boolean)
        .join("\n");

      return html.replace("<!--seo-meta-->", extraMeta);
    },
  };
}
