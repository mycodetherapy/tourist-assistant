import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { config, googleOAuthConfigured } from "../config.js";
import {
  bearerSecurity,
  loginBodySchema,
  ref,
  registerBodySchema,
  settingsBodySchema,
} from "../openapi/components.js";
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
import {
  recordUserLogin,
  recordUserRegister,
} from "../services/authAudit.js";

export async function registerAuthRoutes(app: FastifyInstance): Promise<void> {
  app.post(
    "/api/auth/register",
    {
      schema: {
        tags: ["auth"],
        summary: "Register",
        body: ref("RegisterRequest"),
        response: {
          201: ref("AuthResponse"),
          400: ref("ErrorDetail"),
          409: ref("ErrorDetail"),
        },
      },
    },
    async (request, reply) => {
      const body = registerBodySchema.safeParse(request.body);
      if (!body.success) {
        return reply.code(400).send({ detail: "Некорректные данные" });
      }
      try {
        const { user, token } = await registerUser(
          body.data.email,
          body.data.password,
        );
        await recordUserRegister(user.id, { method: "email" });
        await recordUserLogin(user.id, { method: "email" });
        return reply.code(201).send({
          access_token: token,
          token_type: "bearer",
          user: { id: user.id, email: user.email },
        });
      } catch (err) {
        if (err instanceof AuthError) {
          const code = err.statusCode === 409 ? 409 : 400;
          return reply.code(code).send({ detail: err.message });
        }
        throw err;
      }
    },
  );

  app.post(
    "/api/auth/login",
    {
      schema: {
        tags: ["auth"],
        summary: "Login",
        body: ref("LoginRequest"),
        response: {
          200: ref("AuthResponse"),
          400: ref("ErrorDetail"),
          401: ref("ErrorDetail"),
        },
      },
    },
    async (request, reply) => {
      const body = loginBodySchema.safeParse(request.body);
      if (!body.success) {
        return reply.code(400).send({ detail: "Некорректные данные" });
      }
      try {
        const { user, token } = await loginUser(
          body.data.email,
          body.data.password,
        );
        await recordUserLogin(user.id, { method: "email" });
        return {
          access_token: token,
          token_type: "bearer",
          user: { id: user.id, email: user.email },
        };
      } catch (err) {
        if (err instanceof AuthError) {
          return reply.code(401).send({ detail: err.message });
        }
        throw err;
      }
    },
  );

  app.get(
    "/api/auth/me",
    {
      preHandler: requireAuth,
      schema: {
        tags: ["auth"],
        summary: "Current user",
        security: [...bearerSecurity],
        response: { 200: ref("UserResponse"), 401: ref("ErrorDetail") },
      },
    },
    async (request) => ({
      id: request.user!.id,
      email: request.user!.email,
    }),
  );

  app.post(
    "/api/auth/logout",
    {
      schema: {
        tags: ["auth"],
        summary: "Logout",
        response: { 204: { type: "null", description: "No content" } },
      },
    },
    async (_request, reply) => reply.code(204).send(),
  );

  app.get(
    "/api/auth/google",
    {
      schema: {
        tags: ["auth"],
        summary: "Google OAuth redirect",
        description: "Редирект на Google; callback — /api/auth/google/callback",
      },
    },
    async (request, reply) => {
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
    },
  );

  app.get(
    "/api/auth/google/callback",
    {
      schema: {
        tags: ["auth"],
        summary: "Google OAuth callback",
      },
    },
    async (request, reply) => {
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
        const { token, user, isNewUser } = await loginOrLinkGoogle({
          googleSub: profile.sub,
          email: profile.email,
        });
        if (isNewUser) {
          await recordUserRegister(user.id, { method: "google" });
        }
        await recordUserLogin(user.id, { method: "google" });
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
    },
  );
}

export async function registerProfileRoutes(app: FastifyInstance): Promise<void> {
  app.get(
    "/api/profile",
    {
      preHandler: requireAuth,
      schema: {
        tags: ["profile"],
        security: [...bearerSecurity],
      },
    },
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
    {
      preHandler: requireAuth,
      schema: {
        tags: ["profile"],
        security: [...bearerSecurity],
      },
    },
    async (request) => getLlmSettingsView(request.user!.id),
  );

  app.put(
    "/api/profile/settings",
    {
      preHandler: requireAuth,
      schema: {
        tags: ["profile"],
        security: [...bearerSecurity],
        body: ref("UpdateSettingsRequest"),
      },
    },
    async (request, reply) => {
      const body = settingsBodySchema.safeParse(request.body);
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
    {
      preHandler: requireAuth,
      schema: {
        tags: ["profile"],
        security: [...bearerSecurity],
        response: { 204: { type: "null" } },
      },
    },
    async (request, reply) => {
      await removeLlmKey(request.user!.id);
      return reply.code(204).send();
    },
  );
}
