import type { FastifyReply, FastifyRequest } from "fastify";
import { config } from "../config.js";
import {
  AUTH_COOKIE_NAME,
  createAuthSession,
  deleteAuthSessionById,
  deleteAuthSessionByTokenHash,
  getAuthSessionByTokenHash,
  hashAuthSessionToken,
  newAuthSessionToken,
  touchAuthSession,
  type AuthSessionRow,
} from "../repos/authSessions.js";
import { getUserById, isGuestUser, type User } from "../repos/users.js";
import {
  oauthCookieDomain,
  oauthCookieSecure,
} from "./googleOAuth.js";

export { AUTH_COOKIE_NAME };

function frontendOrigin(frontendUrl?: string): string {
  const raw = (frontendUrl || config.frontendUrl).trim().replace(/\/$/, "");
  return raw || config.frontendUrl;
}

export function authCookieOptions(frontendUrl?: string) {
  const origin = frontendOrigin(frontendUrl);
  const maxAgeSec = Math.max(1, config.authSessionTtlDays) * 86400;
  const domain = oauthCookieDomain(origin);
  return {
    path: "/",
    httpOnly: true,
    sameSite: "lax" as const,
    maxAge: maxAgeSec,
    secure: oauthCookieSecure(origin),
    signed: false,
    ...(domain ? { domain } : {}),
  };
}

export function setAuthSessionCookie(
  reply: FastifyReply,
  rawToken: string,
  frontendUrl?: string,
): void {
  reply.setCookie(AUTH_COOKIE_NAME, rawToken, authCookieOptions(frontendUrl));
}

export function clearAuthSessionCookie(
  reply: FastifyReply,
  frontendUrl?: string,
): void {
  const origin = frontendOrigin(frontendUrl);
  const domain = oauthCookieDomain(origin);
  const base = { path: "/" as const };
  reply.clearCookie(AUTH_COOKIE_NAME, base);
  if (domain) {
    reply.clearCookie(AUTH_COOKIE_NAME, { ...base, domain });
  }
}

export async function issueAuthSession(
  request: FastifyRequest,
  reply: FastifyReply,
  userId: number,
  frontendUrl?: string,
): Promise<void> {
  const raw = newAuthSessionToken();
  const expiresAt = new Date(
    Date.now() + Math.max(1, config.authSessionTtlDays) * 86400 * 1000,
  );
  const ua = request.headers["user-agent"];
  await createAuthSession({
    userId,
    tokenHash: hashAuthSessionToken(raw),
    expiresAt,
    userAgent: typeof ua === "string" ? ua : null,
  });
  setAuthSessionCookie(reply, raw, frontendUrl);
}

function rawCookieToken(request: FastifyRequest): string | null {
  const raw = request.cookies?.[AUTH_COOKIE_NAME]?.trim();
  return raw || null;
}

export async function loadAuthSession(
  request: FastifyRequest,
): Promise<{ session: AuthSessionRow; user: User } | null> {
  const raw = rawCookieToken(request);
  if (!raw) return null;
  const session = await getAuthSessionByTokenHash(hashAuthSessionToken(raw));
  if (!session) return null;
  if (Date.parse(session.expires_at) <= Date.now()) {
    await deleteAuthSessionById(session.id);
    return null;
  }
  const user = await getUserById(session.user_id);
  if (!user || (await isGuestUser(session.user_id))) {
    await deleteAuthSessionById(session.id);
    return null;
  }
  void touchAuthSession(session.id, config.authSessionTtlDays).catch(() => {});
  return { session, user };
}

export async function destroyAuthSession(
  request: FastifyRequest,
  reply: FastifyReply,
  frontendUrl?: string,
): Promise<void> {
  const raw = rawCookieToken(request);
  if (raw) {
    await deleteAuthSessionByTokenHash(hashAuthSessionToken(raw));
  }
  clearAuthSessionCookie(reply, frontendUrl);
}
