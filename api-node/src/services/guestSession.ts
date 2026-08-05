import type { FastifyReply, FastifyRequest } from "fastify";
import { config } from "../config.js";
import {
  createGuestSession,
  getGuestSessionById,
  GUEST_COOKIE_NAME,
  type GuestSessionRow,
} from "../repos/guestSessions.js";
import { createGuestUser, getUserById } from "../repos/users.js";
import { guestSessionExpired } from "./guestQuotas.js";

export interface GuestContext {
  session: GuestSessionRow;
  userId: number;
}

function guestCookieOptions() {
  const maxAgeSec = config.guestSessionTtlDays * 86400;
  return {
    path: "/",
    httpOnly: true,
    sameSite: "lax" as const,
    maxAge: maxAgeSec,
    secure: config.guestCookieSecure,
    signed: false,
  };
}

export function setGuestSessionCookie(
  reply: FastifyReply,
  sessionId: string,
): void {
  reply.setCookie(GUEST_COOKIE_NAME, sessionId, guestCookieOptions());
}

export function clearGuestSessionCookie(reply: FastifyReply): void {
  reply.clearCookie(GUEST_COOKIE_NAME, { path: "/" });
}

export async function ensureGuestSession(
  request: FastifyRequest,
  reply: FastifyReply,
): Promise<GuestContext> {
  const raw = request.cookies?.[GUEST_COOKIE_NAME]?.trim();
  if (raw) {
    const existing = await getGuestSessionById(raw);
    if (existing && !guestSessionExpired(existing)) {
      const user = await getUserById(existing.user_id);
      if (user) {
        return { session: existing, userId: existing.user_id };
      }
    }
  }

  const user = await createGuestUser();
  const expiresAt = new Date(
    Date.now() + config.guestSessionTtlDays * 86400 * 1000,
  );
  const session = await createGuestSession({ userId: user.id, expiresAt });
  setGuestSessionCookie(reply, session.id);
  return { session, userId: user.id };
}

export async function loadGuestSession(
  request: FastifyRequest,
): Promise<GuestContext | null> {
  const raw = request.cookies?.[GUEST_COOKIE_NAME]?.trim();
  if (!raw) return null;
  const session = await getGuestSessionById(raw);
  if (!session || guestSessionExpired(session)) return null;
  const user = await getUserById(session.user_id);
  if (!user) return null;
  return { session, userId: session.user_id };
}

export async function claimGuestSessionForUser(
  request: FastifyRequest,
  reply: FastifyReply,
  targetUserId: number,
): Promise<number | null> {
  const ctx = await loadGuestSession(request);
  if (!ctx) return null;
  const { transferGuestUserData } = await import("../repos/guestSessions.js");
  const tripId = await transferGuestUserData(ctx.userId, targetUserId);
  clearGuestSessionCookie(reply);
  return tripId;
}
