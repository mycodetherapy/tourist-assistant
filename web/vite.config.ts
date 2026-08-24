import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import basicSsl from "@vitejs/plugin-basic-ssl";
import { defineConfig, loadEnv } from "vite";
import { VitePWA } from "vite-plugin-pwa";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)));
const repoRoot = path.resolve(webRoot, "..");

/** Docker web-образ: context ./web → repoRoot=/, .env лежит в web/.env. Локально — корневой .env. */
function resolveEnvDir(): string {
  if (fs.existsSync(path.join(repoRoot, ".env"))) {
    return repoRoot;
  }
  if (fs.existsSync(path.join(webRoot, ".env"))) {
    return webRoot;
  }
  return repoRoot;
}

function mergeEnv(mode: string): Record<string, string> {
  const fromRepo = loadEnv(mode, repoRoot, "");
  const fromWeb = loadEnv(mode, webRoot, "");
  return { ...fromRepo, ...fromWeb };
}

/** IPv4 Mac в LAN — иначе HMR с телефона цепляется к localhost (чёрный экран). */
function resolveLanIp(env: Record<string, string>): string | undefined {
  const override = env.VITE_HMR_HOST?.trim();
  if (override) return override;
  for (const ifaces of Object.values(os.networkInterfaces())) {
    if (!ifaces) continue;
    for (const iface of ifaces) {
      if (iface.family === "IPv4" && !iface.internal) {
        return iface.address;
      }
    }
  }
  return undefined;
}

export default defineConfig(({ mode }) => {
  const envDir = resolveEnvDir();
  const env = mergeEnv(mode);
  // Node API (api-node) — :8001; FastAPI legacy — VITE_API_PORT=8000
  const apiPort = env.VITE_API_PORT || env.API_NODE_PORT || "8001";
  const apiTarget = `http://127.0.0.1:${apiPort}`;
  const lanIp = resolveLanIp(env);
  // HTTPS по умолчанию при доступе с телефона по LAN — иначе геолокация зависает на http://IP:5173
  const devHttps = env.VITE_DEV_HTTPS === "true" || (env.VITE_DEV_HTTPS !== "false" && Boolean(lanIp));
  console.log(`[vite] envDir → ${envDir}`);
  console.log(`[vite] API proxy → ${apiTarget}`);
  if (lanIp) {
    const scheme = devHttps ? "https" : "http";
    console.log(`[vite] Phone / PWA dev URL → ${scheme}://${lanIp}:5173`);
    console.log(`[vite] HMR websocket host → ${lanIp}`);
    if (!devHttps) {
      console.log("[vite] Geolocation on phone needs HTTPS — unset VITE_DEV_HTTPS=false or use https://…");
    } else {
      console.log("[vite] HTTPS enabled for geolocation on phone (trust the certificate once in browser)");
    }
  }

  return {
  envDir,
  plugins: [
    ...(devHttps
      ? [
          basicSsl({
            name: "tourist-assistant-dev",
            domains: ["localhost", "127.0.0.1", ...(lanIp ? [lanIp] : [])],
          }),
        ]
      : []),
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "apple-touch-icon.png", "icons/icon-192.png", "icons/icon-512.png"],
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        // maplibre + antd раздувают chunk выше дефолтных 2 MiB
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
        // /docs — Swagger на api-node; без denylist SW отдаёт старый index.html (лендинг)
        navigateFallbackDenylist: [/^\/docs/, /^\/api\//, /^\/health$/],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith("/api/"),
            handler: "NetworkFirst",
            options: {
              cacheName: "api-cache",
              networkTimeoutSeconds: 10,
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
        ],
      },
      manifest: {
        name: "Прогуляй — пешие маршруты",
        short_name: "Прогуляй",
        description: "Три варианта пешей прогулки по городу — карта маршрута и ссылка на Яндекс.Карты",
        theme_color: "#001529",
        background_color: "#f5f5f5",
        display: "standalone",
        orientation: "portrait-primary",
        start_url: "/",
        lang: "ru",
        scope: "/",
        icons: [
          {
            src: "icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
    }),
  ],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    // HTTPS-сертификат задаёт @vitejs/plugin-basic-ssl (совместим с мобильными браузерами)
    // Без host телефон грузит HTML, но /@vite/client вешается на ws://localhost
    hmr: lanIp
      ? {
          host: lanIp,
          port: 5173,
          clientPort: 5173,
          protocol: devHttps ? "wss" : "ws",
        }
      : devHttps
        ? { port: 5173, clientPort: 5173, protocol: "wss" }
        : true,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
      "/health": {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
};
});
