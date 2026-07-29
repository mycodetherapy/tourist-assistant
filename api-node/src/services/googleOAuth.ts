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

export function buildGoogleAuthorizeUrl(frontendUrl: string): {
  url: string;
  state: string;
} {
  if (!googleOAuthConfigured()) {
    throw new AuthError("Google OAuth не настроен", 503);
  }
  const nonce = randomBytes(16).toString("hex");
  const state = signState(nonce);
  const params = new URLSearchParams({
    client_id: config.googleClientId,
    redirect_uri: config.googleRedirectUri(),
    response_type: "code",
    scope: "openid email profile",
    state,
    access_type: "online",
    prompt: "select_account",
  });
  return { url: `${GOOGLE_AUTH_URL}?${params}`, state };
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
    return {
      user: bySub,
      token: createAccessToken(bySub.id, bySub.email),
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
  });
  return {
    user,
    token: createAccessToken(user.id, user.email),
    isNewUser: true,
  };
}

export async function exchangeGoogleCode(code: string): Promise<{
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
    redirect_uri: config.googleRedirectUri(),
    grant_type: "authorization_code",
  });
  const tokenRes = await fetch(GOOGLE_TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    signal: AbortSignal.timeout(15000),
  });
  if (!tokenRes.ok) {
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
  const raw = (queryFrontend || cookieFrontend || config.frontendUrl).trim();
  return raw.replace(/\/$/, "") || config.frontendUrl;
}

export function oauthCookieNames(): {
  state: string;
  frontend: string;
} {
  return { state: OAUTH_COOKIE, frontend: OAUTH_FRONTEND_COOKIE };
}

export function verifyOAuthState(state: string | undefined): boolean {
  return Boolean(state && verifyState(state));
}
