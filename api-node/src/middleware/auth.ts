import type { FastifyReply, FastifyRequest } from "fastify";
import { decodeAccessToken } from "../lib/crypto.js";
import { AuthError, userFromTokenSub } from "../services/auth.js";
import { touchUserLastSeen } from "../repos/users.js";
import type { User } from "../repos/users.js";

declare module "fastify" {
  interface FastifyRequest {
    user?: User;
  }
}

export async function requireAuth(
  request: FastifyRequest,
  reply: FastifyReply,
): Promise<void> {
  const header = request.headers.authorization;
  if (!header?.startsWith("Bearer ")) {
    reply.code(401).send({ detail: "Требуется авторизация" });
    return;
  }
  const token = header.slice(7);
  try {
    const payload = decodeAccessToken(token);
    request.user = await userFromTokenSub(payload.sub);
    void touchUserLastSeen(request.user.id).catch(() => {});
  } catch (err) {
    if (err instanceof AuthError) {
      reply.code(err.statusCode).send({ detail: err.message });
      return;
    }
    reply.code(401).send({ detail: "Недействительный токен" });
  }
}
