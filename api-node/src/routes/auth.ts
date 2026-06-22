import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { config, googleOAuthConfigured } from "../config.js";
import {
  AuthError,
  getLlmSettingsView,
  loginUser,
  registerUser,
  removeLlmKey,
  saveLlmSettings,
} from "../services/auth.js";
import {
  buildGoogleAuthorizeUrl,
  exchangeGoogleCode,
  loginOrLinkGoogle,
  oauthCookieNames,
  resolveFrontendUrl,
  verifyOAuthState,
} from "../services/googleOAuth.js";
import { requireAuth } from "../middleware/auth.js";

const registerSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

const loginSchema = registerSchema;

const settingsSchema = z.object({
  llm_api_key: z.string().max(256).nullable().optional(),
  llm_base_url: z.string().max(512).nullable().optional(),
  llm_model: z.string().max(128).nullable().optional(),
});

export async function registerAuthRoutes(app: FastifyInstance): Promise<void> {
  app.post("/api/auth/register", async (request, reply) => {
    const body = registerSchema.safeParse(request.body);
    if (!body.success) {
      return reply.code(400).send({ detail: "Некорректные данные" });
    }
    try {
      const { user, token } = await registerUser(
        body.data.email,
        body.data.password,
      );
      return reply.code(201).send({
        access_token: token,
        token_type: "bearer",
        user: { id: user.id, email: user.email },
      });
    } catch (err) {
      if (err instanceof AuthError) {
        return reply.code(err.statusCode).send({ detail: err.message });
      }
      throw err;
    }
  });

  app.post("/api/auth/login", async (request, reply) => {
    const body = loginSchema.safeParse(request.body);
    if (!body.success) {
      return reply.code(400).send({ detail: "Некорректные данные" });
    }
    try {
      const { user, token } = await loginUser(
        body.data.email,
        body.data.password,
      );
      return {
        access_token: token,
        token_type: "bearer",
        user: { id: user.id, email: user.email },
      };
    } catch (err) {
      if (err instanceof AuthError) {
        return reply.code(err.statusCode).send({ detail: err.message });
      }
      throw err;
    }
  });

  app.get(
    "/api/auth/me",
    { preHandler: requireAuth },
    async (request) => ({
      id: request.user!.id,
      email: request.user!.email,
    }),
  );

  app.post("/api/auth/logout", async (_request, reply) => {
    return reply.code(204).send();
  });

  app.get("/api/auth/google", async (request, reply) => {
    if (!googleOAuthConfigured()) {
      return reply.code(503).send({ detail: "Google OAuth не настроен" });
    }
    const frontend =
      typeof request.query === "object" &&
      request.query !== null &&
      "frontend" in request.query
        ? String((request.query as { frontend?: string }).frontend ?? "")
        : "";
    const frontendUrl = resolveFrontendUrl(frontend, undefined);
    try {
      const { url, state } = buildGoogleAuthorizeUrl(frontendUrl);
      const cookies = oauthCookieNames();
      reply
        .setCookie(cookies.state, state, {
          path: "/",
          httpOnly: true,
          sameSite: "lax",
          maxAge: 600,
          secure: config.port === 443,
        })
        .setCookie(cookies.frontend, frontendUrl, {
          path: "/",
          httpOnly: true,
          sameSite: "lax",
          maxAge: 600,
          secure: config.port === 443,
        });
      return reply.redirect(url);
    } catch (err) {
      if (err instanceof AuthError) {
        return reply.code(err.statusCode).send({ detail: err.message });
      }
      throw err;
    }
  });

  app.get("/api/auth/google/callback", async (request, reply) => {
    if (!googleOAuthConfigured()) {
      return reply.code(503).send({ detail: "Google OAuth не настроен" });
    }
    const query = request.query as {
      code?: string;
      state?: string;
      frontend?: string;
    };
    const cookies = oauthCookieNames();
    const cookieState = request.cookies?.[cookies.state];
    if (!verifyOAuthState(query.state) || query.state !== cookieState) {
      return reply.code(400).send({ detail: "Ошибка авторизации Google" });
    }
    if (!query.code) {
      return reply.code(400).send({ detail: "Ошибка авторизации Google" });
    }
    try {
      const profile = await exchangeGoogleCode(query.code);
      const { token } = await loginOrLinkGoogle({
        googleSub: profile.sub,
        email: profile.email,
      });
      const frontend = resolveFrontendUrl(
        query.frontend,
        request.cookies?.[cookies.frontend],
      );
      reply
        .clearCookie(cookies.state, { path: "/" })
        .clearCookie(cookies.frontend, { path: "/" });
      const redirectUrl = `${frontend}/auth/callback?token=${encodeURIComponent(token)}`;
      return reply.redirect(redirectUrl);
    } catch (err) {
      if (err instanceof AuthError) {
        return reply.code(err.statusCode).send({ detail: err.message });
      }
      return reply.code(400).send({ detail: "Ошибка авторизации Google" });
    }
  });
}

export async function registerProfileRoutes(app: FastifyInstance): Promise<void> {
  app.get(
    "/api/profile",
    { preHandler: requireAuth },
    async (request) => {
      const { getUserProfile } = await import("../repos/users.js");
      const { normalizeTripPreferences } = await import("../lib/preferences.js");
      const data = await getUserProfile(request.user!.id);
      return {
        preferences: data ? normalizeTripPreferences(data) : null,
      };
    },
  );

  app.get(
    "/api/profile/settings",
    { preHandler: requireAuth },
    async (request) => getLlmSettingsView(request.user!.id),
  );

  app.put(
    "/api/profile/settings",
    { preHandler: requireAuth },
    async (request, reply) => {
      const body = settingsSchema.safeParse(request.body);
      if (!body.success) {
        return reply.code(400).send({ detail: "Некорректные данные" });
      }
      try {
        await saveLlmSettings(request.user!.id, body.data);
        return getLlmSettingsView(request.user!.id);
      } catch (err) {
        if (err instanceof AuthError) {
          return reply.code(err.statusCode).send({ detail: err.message });
        }
        throw err;
      }
    },
  );

  app.delete(
    "/api/profile/settings/llm-key",
    { preHandler: requireAuth },
    async (request, reply) => {
      await removeLlmKey(request.user!.id);
      return reply.code(204).send();
    },
  );
}
