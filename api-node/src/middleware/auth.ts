import type { FastifyReply, FastifyRequest } from "fastify";
import { decodeAccessToken } from "../lib/crypto.js";
import { AuthError, userFromTokenSub } from "../services/auth.js";
import {
  AUTH_COOKIE_NAME,
  issueAuthSession,
  loadAuthSession,
} from "../services/authSession.js";
import { touchUserLastSeen } from "../repos/users.js";
import type { User } from "../repos/users.js";

declare module "fastify" {
  interface FastifyRequest {
    user?: User;
  }
}

async function userFromBearer(request: FastifyRequest): Promise<User | null> {
  const header = request.headers.authorization;
  if (!header?.startsWith("Bearer ")) return null;
  const payload = decodeAccessToken(header.slice(7));
  return userFromTokenSub(payload.sub);
}

/** Cookie-сессия или JWT Bearer (запасной вариант). */
export async function resolveRequestUser(
  request: FastifyRequest,
): Promise<User | null> {
  const fromCookie = await loadAuthSession(request);
  if (fromCookie) {
    return fromCookie.user;
  }
  try {
    return await userFromBearer(request);
  } catch {
    return null;
  }
}

export async function requireAuth(
  request: FastifyRequest,
  reply: FastifyReply,
): Promise<void> {
  try {
    const fromCookie = await loadAuthSession(request);
    if (fromCookie) {
      request.user = fromCookie.user;
      void touchUserLastSeen(request.user.id).catch(() => {});
      return;
    }
    const header = request.headers.authorization;
    if (!header?.startsWith("Bearer ")) {
      reply.code(401).send({ detail: "Требуется авторизация" });
      return;
    }
    const payload = decodeAccessToken(header.slice(7));
    request.user = await userFromTokenSub(payload.sub);
    void touchUserLastSeen(request.user.id).catch(() => {});
    if (!request.cookies?.[AUTH_COOKIE_NAME]?.trim()) {
      await issueAuthSession(request, reply, request.user.id);
    }
  } catch (err) {
    if (err instanceof AuthError) {
      reply.code(err.statusCode).send({ detail: err.message });
      return;
    }
    reply.code(401).send({ detail: "Недействительный токен" });
  }
}
