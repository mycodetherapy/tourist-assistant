import "./loadEnv.js";

const DEFAULT_LLM_BASE_URL = "https://openai.api.proxyapi.ru/v1";
const DEFAULT_LLM_MODEL = "gemini/gemini-2.5-flash";

function required(name: string, value: string | undefined): string {
  const v = (value ?? "").trim();
  if (!v) {
    throw new Error(`${name} is required`);
  }
  return v;
}

function parseDatabaseUrl(raw: string): string {
  return raw.replace(/^postgresql\+psycopg:/, "postgresql:");
}

/** Как auth/jwt_tokens.py: невалидный JWT_ACCESS_TTL_MINUTES → 60 мин. */
function parseJwtTtlMinutes(raw: string | undefined): number {
  const trimmed = (raw ?? "60").trim();
  const n = Number(trimmed);
  if (!Number.isFinite(n)) {
    return 60;
  }
  return Math.max(5, Math.floor(n));
}

export const config = {
  port: Number(process.env.API_NODE_PORT ?? process.env.PORT ?? 8001),
  jwtSecret: () => required("JWT_SECRET", process.env.JWT_SECRET),
  jwtTtlMinutes: parseJwtTtlMinutes(process.env.JWT_ACCESS_TTL_MINUTES),
  settingsEncryptionKey: () =>
    required("SETTINGS_ENCRYPTION_KEY", process.env.SETTINGS_ENCRYPTION_KEY),
  databaseUrl: () =>
    parseDatabaseUrl(required("DATABASE_URL", process.env.DATABASE_URL)),
  redisUrl: (process.env.REDIS_URL ?? "").trim(),
  corsOrigins: (process.env.CORS_ORIGINS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
  defaultLlmBaseUrl: process.env.LLM_BASE_URL?.trim() || DEFAULT_LLM_BASE_URL,
  defaultLlmModel: process.env.LLM_MODEL?.trim() || DEFAULT_LLM_MODEL,
  runQuotaFullPerHour: Number(process.env.RUN_QUOTA_FULL_PER_HOUR ?? 10),
  runQuotaPartialPerHour: Number(process.env.RUN_QUOTA_PARTIAL_PER_HOUR ?? 10),
  runQuotaWindowSec: Number(process.env.RUN_QUOTA_WINDOW_SEC ?? 3600),
  runQuotasEnabled: !["0", "false", "no", "off"].includes(
    (process.env.RUN_QUOTAS_ENABLED ?? "true").trim().toLowerCase(),
  ),
  freeRunQuotaPerDay: Number(process.env.FREE_RUN_QUOTA_PER_DAY ?? 30),
  freeRunQuotaWindowSec: Number(process.env.FREE_RUN_QUOTA_WINDOW_SEC ?? 86400),
  freeRunQuotasEnabled: !["0", "false", "no", "off"].includes(
    (process.env.FREE_RUN_QUOTAS_ENABLED ?? "true").trim().toLowerCase(),
  ),
  estimatedAiRunCostRub: Number(process.env.ESTIMATED_AI_RUN_COST_RUB ?? 4),
  graphRunStaleSec: Number(process.env.GRAPH_RUN_STALE_SEC ?? 600),
  yandexMapsApiKey: (process.env.YANDEX_MAPS_API_KEY ?? "").trim(),
  googleClientId: (process.env.GOOGLE_CLIENT_ID ?? "").trim(),
  googleClientSecret: (process.env.GOOGLE_CLIENT_SECRET ?? "").trim(),
  googleRedirectUri: () => {
    const raw =
      process.env.GOOGLE_REDIRECT_URI?.trim() ||
      `http://localhost:${config.port}/api/auth/google/callback`;
    return raw;
  },
  frontendUrl: (process.env.FRONTEND_URL ?? "http://localhost:5173").replace(
    /\/$/,
    "",
  ),
};

export function googleOAuthConfigured(): boolean {
  return Boolean(config.googleClientId && config.googleClientSecret);
}

export function isPlaceholderSecret(value: string): boolean {
  const v = value.trim().toLowerCase();
  return (
    !v ||
    v.includes("change-me") ||
    v.includes("your-") ||
    v.includes("sk-or-...") ||
    v === "sk-or-v1-..." ||
    v.startsWith("sk-or-xxx")
  );
}
