import { createHmac, randomBytes } from "node:crypto";
import { config, googleOAuthConfigured } from "../config.js";
import { createAccessToken } from "../lib/crypto.js";
import {
  createUser,
  getUserByEmail,
  getUserByGoogleSub,
  getUserById,
  linkGoogleSub,
  type User,
} from "../repos/users.js";
import { AuthError } from "./auth.js";

const GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth";
const GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token";
const GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo";
const OAUTH_COOKIE = "oauth_state";
const OAUTH_FRONTEND_COOKIE = "oauth_frontend";
const OAUTH_REDIRECT_COOKIE = "oauth_redirect";

function signState(nonce: string): string {
  const sig = createHmac("sha256", config.jwtSecret())
    .update(nonce)
    .digest("base64url");
  return `${nonce}.${sig}`;
}

function verifyState(state: string): boolean {
  const [nonce, sig] = state.split(".");
  if (!nonce || !sig) return false;
  const expected = createHmac("sha256", config.jwtSecret())
    .update(nonce)
    .digest("base64url");
  return sig === expected;
}

function defaultFrontendOrigin(): string {
  return (process.env.FRONTEND_URL ?? config.frontendUrl).replace(/\/$/, "");
}

function isValidIpv4(hostname: string): boolean {
  const parts = hostname.split(".");
  if (parts.length !== 4) return false;
  return parts.every((part) => {
    if (!/^\d{1,3}$/.test(part)) return false;
    const value = Number(part);
    return value >= 0 && value <= 255;
  });
}

function isLoopbackHostname(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1";
}

function effectivePort(url: URL): string {
  if (url.port) return url.port;
  return url.protocol === "https:" ? "443" : "80";
}

function isStrictOriginUrl(origin: string): boolean {
  try {
    const url = new URL(origin);
    if (url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
      return false;
    }
    if (url.protocol !== "http:" && url.protocol !== "https:") return false;
    const { hostname } = url;
    return isLoopbackHostname(hostname) || isValidIpv4(hostname);
  } catch {
    return false;
  }
}

function addWwwVariant(allowed: Set<string>, origin: string): void {
  try {
    const url = new URL(origin);
    if (isLoopbackHostname(url.hostname) || isValidIpv4(url.hostname)) {
      return;
    }
    if (!url.hostname.startsWith("www.")) {
      allowed.add(`${url.protocol}//www.${url.hostname}`);
    }
  } catch {
    /* ignore invalid origin */
  }
}

function configuredFrontendOrigins(): Set<string> {
  const allowed = new Set<string>();
  const frontend = (process.env.FRONTEND_URL ?? "http://localhost:5173")
    .trim()
    .replace(/\/$/, "");
  if (frontend) allowed.add(frontend);
  const corsRaw = process.env.CORS_ORIGINS ?? "";
  for (const item of corsRaw.split(",")) {
    const origin = item.trim().replace(/\/$/, "");
    if (origin) allowed.add(origin);
  }
  for (const origin of [...allowed]) {
    addWwwVariant(allowed, origin);
  }
  return allowed;
}

export function isAllowedFrontendOrigin(origin: string): boolean {
  const normalized = origin.trim().replace(/\/$/, "");
  if (!normalized) return false;

  if (configuredFrontendOrigins().has(normalized)) return true;

  return isStrictOriginUrl(normalized);
}

export function oauthRedirectOrigin(frontendUrl: string): string {
  const normalized = frontendUrl.trim().replace(/\/$/, "");
  const fallback = defaultFrontendOrigin();

  if (!normalized || !isAllowedFrontendOrigin(normalized)) {
    return fallback;
  }

  if (configuredFrontendOrigins().has(normalized)) {
    return normalized;
  }

  const devBase = defaultFrontendOrigin();
  if (!isAllowedFrontendOrigin(devBase)) {
    return normalized;
  }

  try {
    const current = new URL(normalized);
    const canonical = new URL(devBase);
    if (
      isLoopbackHostname(current.hostname) &&
      isLoopbackHostname(canonical.hostname) &&
      effectivePort(current) === effectivePort(canonical)
    ) {
      return canonical.origin;
    }
  } catch {
    return fallback;
  }

  return normalized;
}

export function googleOAuthRedirectUri(frontendUrl: string): string {
  return `${oauthRedirectOrigin(frontendUrl)}/api/auth/google/callback`;
}

export function inferFrontendOrigin(referer: string | undefined): string | undefined {
  if (!referer) return undefined;
  try {
    return new URL(referer).origin;
  } catch {
    return undefined;
  }
}

export function buildGoogleAuthorizeUrl(frontendUrl: string): {
  url: string;
  state: string;
  redirectUri: string;
} {
  if (!googleOAuthConfigured()) {
    throw new AuthError("Google OAuth не настроен", 503);
  }
  const redirectUri = googleOAuthRedirectUri(frontendUrl);
  const nonce = randomBytes(16).toString("hex");
  const state = signState(nonce);
  const params = new URLSearchParams({
    client_id: config.googleClientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: "openid email profile",
    state,
    access_type: "online",
    prompt: "select_account",
  });
  return { url: `${GOOGLE_AUTH_URL}?${params}`, state, redirectUri };
}

export async function loginOrLinkGoogle(params: {
  googleSub: string;
  email: string;
}): Promise<{ user: User; token: string; isNewUser: boolean }> {
  const email = params.email.trim().toLowerCase();
  if (!email || !params.googleSub) {
    throw new AuthError("Google не вернул email", 400);
  }

  const bySub = await getUserByGoogleSub(params.googleSub);
  if (bySub) {
    const { markEmailVerified } = await import("../repos/users.js");
    await markEmailVerified(bySub.id);
    const user = (await getUserById(bySub.id))!;
    return {
      user,
      token: createAccessToken(user.id, user.email),
      isNewUser: false,
    };
  }

  const byEmail = await getUserByEmail(email);
  if (byEmail) {
    if (byEmail.google_sub && byEmail.google_sub !== params.googleSub) {
      throw new AuthError("Email уже привязан к другому Google-аккаунту", 409);
    }
    if (!byEmail.google_sub) {
      await linkGoogleSub(byEmail.id, params.googleSub);
    }
    const user = (await getUserById(byEmail.id))!;
    return {
      user,
      token: createAccessToken(user.id, user.email),
      isNewUser: false,
    };
  }

  const user = await createUser({
    email,
    google_sub: params.googleSub,
    email_verified: true,
  });
  return {
    user,
    token: createAccessToken(user.id, user.email),
    isNewUser: true,
  };
}

export function oauthCookieSecure(frontendUrl: string): boolean {
  try {
    return new URL(frontendUrl).protocol === "https:";
  } catch {
    return false;
  }
}

/** Shared cookie domain for apex + www on prod (e.g. `.progulyai.ru`). */
export function oauthCookieDomain(frontendUrl: string): string | undefined {
  try {
    const url = new URL(frontendUrl.trim().replace(/\/$/, ""));
    if (isLoopbackHostname(url.hostname) || isValidIpv4(url.hostname)) {
      return undefined;
    }
    const parts = url.hostname.toLowerCase().split(".");
    if (parts.length >= 2) {
      return `.${parts.slice(-2).join(".")}`;
    }
  } catch {
    return undefined;
  }
  return undefined;
}

export function oauthLoginErrorUrl(frontendUrl: string, code: string): string {
  const base = oauthRedirectOrigin(frontendUrl);
  return `${base}/login?error=${encodeURIComponent(code)}`;
}

export function isAllowedRedirectUri(uri: string): boolean {
  try {
    const parsed = new URL(uri);
    if (parsed.pathname !== "/api/auth/google/callback") return false;
    return isAllowedFrontendOrigin(parsed.origin);
  } catch {
    return false;
  }
}

export async function exchangeGoogleCode(
  code: string,
  redirectUri: string,
  logError?: (message: string, extra?: Record<string, unknown>) => void,
): Promise<{
  sub: string;
  email: string;
}> {
  if (!googleOAuthConfigured()) {
    throw new AuthError("Google OAuth не настроен", 503);
  }
  const body = new URLSearchParams({
    code,
    client_id: config.googleClientId,
    client_secret: config.googleClientSecret,
    redirect_uri: redirectUri,
    grant_type: "authorization_code",
  });
  const tokenRes = await fetch(GOOGLE_TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    signal: AbortSignal.timeout(15000),
  });
  if (!tokenRes.ok) {
    let googleError = "";
    try {
      const errBody = (await tokenRes.json()) as {
        error?: string;
        error_description?: string;
      };
      googleError = [errBody.error, errBody.error_description]
        .filter(Boolean)
        .join(": ");
    } catch {
      googleError = await tokenRes.text().catch(() => "");
    }
    logError?.("Google token exchange failed", {
      status: tokenRes.status,
      redirectUri,
      googleError: googleError.slice(0, 500),
    });
    throw new AuthError("Ошибка авторизации Google", 400);
  }
  const tokenData = (await tokenRes.json()) as { access_token?: string };
  if (!tokenData.access_token) {
    throw new AuthError("Ошибка авторизации Google", 400);
  }
  const userRes = await fetch(GOOGLE_USERINFO_URL, {
    headers: { Authorization: `Bearer ${tokenData.access_token}` },
    signal: AbortSignal.timeout(15000),
  });
  if (!userRes.ok) {
    throw new AuthError("Нет данных профиля Google", 400);
  }
  const userinfo = (await userRes.json()) as { sub?: string; email?: string };
  if (!userinfo.sub || !userinfo.email) {
    throw new AuthError("Google не вернул email", 400);
  }
  return { sub: userinfo.sub, email: userinfo.email };
}

export function resolveFrontendUrl(
  queryFrontend: string | undefined,
  cookieFrontend: string | undefined,
): string {
  for (const raw of [queryFrontend, cookieFrontend]) {
    const candidate = (raw ?? "").trim().replace(/\/$/, "");
    if (candidate && isAllowedFrontendOrigin(candidate)) {
      return candidate;
    }
  }
  return defaultFrontendOrigin() || config.frontendUrl;
}

export function oauthCookieNames(): {
  state: string;
  frontend: string;
  redirect: string;
} {
  return {
    state: OAUTH_COOKIE,
    frontend: OAUTH_FRONTEND_COOKIE,
    redirect: OAUTH_REDIRECT_COOKIE,
  };
}

export function resolveOAuthRedirectUri(
  cookieRedirect: string | undefined,
  frontendUrl: string,
): string {
  const fromCookie = (cookieRedirect ?? "").trim();
  if (fromCookie && isAllowedRedirectUri(fromCookie)) {
    return fromCookie;
  }
  return googleOAuthRedirectUri(frontendUrl);
}

export function verifyOAuthState(state: string | undefined): boolean {
  return Boolean(state && verifyState(state));
}
