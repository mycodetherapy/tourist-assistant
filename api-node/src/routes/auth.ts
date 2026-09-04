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
  resendEmailVerification,
  verifyEmailToken,
} from "../services/emailVerify.js";
import { claimGuestSessionForUser } from "../services/guestSession.js";
import {
  buildGoogleAuthorizeUrl,
  exchangeGoogleCode,
  inferFrontendOrigin,
  loginOrLinkGoogle,
  oauthCookieDomain,
  oauthCookieNames,
  oauthCookieSecure,
  oauthLoginErrorUrl,
  resolveFrontendUrl,
  resolveOAuthRedirectUri,
  verifyOAuthState,
} from "../services/googleOAuth.js";
import { requireAuth } from "../middleware/auth.js";
import { resolveOsrmPrepareQuota } from "../services/osrmPrepareAccess.js";
import {
  recordUserLogin,
  recordUserRegister,
} from "../services/authAudit.js";
import { isEmailVerified, type User } from "../repos/users.js";
import { createAccessToken } from "../lib/crypto.js";

function trimAuthBody(body: unknown): unknown {
  if (!body || typeof body !== "object") return body;
  const record = body as { email?: unknown; password?: unknown };
  if (typeof record.email === "string") {
    record.email = record.email.trim();
  }
  return record;
}

function userPublic(user: User) {
  return {
    id: Number(user.id),
    email: user.email.trim().toLowerCase(),
    email_verified: isEmailVerified(user),
  };
}

function authResponsePayload(
  user: User,
  token: string,
  claimedTripId?: number | null,
) {
  return {
    access_token: token,
    token_type: "bearer" as const,
    user: userPublic(user),
    ...(claimedTripId != null ? { claimed_trip_id: claimedTripId } : {}),
  };
}

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
      preValidation: async (request) => {
        request.body = trimAuthBody(request.body);
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
        try {
          await recordUserRegister(user.id, { method: "email" });
          await recordUserLogin(user.id, { method: "email" });
        } catch (auditErr) {
          request.log.warn({ err: auditErr }, "Register audit failed");
        }
        const claimedTripId = await claimGuestSessionForUser(
          request,
          reply,
          user.id,
        );
        return reply
          .code(201)
          .send(authResponsePayload(user, token, claimedTripId));
      } catch (err) {
        if (err instanceof AuthError) {
          const code = err.statusCode === 409 ? 409 : 400;
          return reply.code(code).send({ detail: err.message });
        }
        request.log.error({ err }, "Register failed");
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
      preValidation: async (request) => {
        request.body = trimAuthBody(request.body);
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
        try {
          await recordUserLogin(user.id, { method: "email" });
        } catch (auditErr) {
          request.log.warn({ err: auditErr }, "Login audit failed");
        }
        const claimedTripId = await claimGuestSessionForUser(
          request,
          reply,
          user.id,
        );
        return reply
          .code(200)
          .send(authResponsePayload(user, token, claimedTripId));
      } catch (err) {
        if (err instanceof AuthError) {
          return reply.code(401).send({ detail: err.message });
        }
        request.log.error({ err }, "Login failed");
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
    async (request) => {
      const quota = await resolveOsrmPrepareQuota(request.user!.id);
      return {
        ...userPublic(request.user!),
        osrm_prepare_quota_used: request.user!.osrm_prepare_quota_used ?? 0,
        osrm_prepare_quota_limit: quota.limit,
        osrm_prepare_quota_unlimited: quota.unlimited,
      };
    },
  );

  app.post(
    "/api/auth/verify-email",
    {
      schema: {
        tags: ["auth"],
        summary: "Confirm email via token from letter",
        body: {
          type: "object",
          required: ["token"],
          properties: { token: { type: "string" } },
        },
        response: {
          200: ref("AuthResponse"),
          400: ref("ErrorDetail"),
        },
      },
    },
    async (request, reply) => {
      const body = z.object({ token: z.string().min(16) }).safeParse(request.body);
      if (!body.success) {
        return reply.code(400).send({ detail: "Некорректный токен" });
      }
      try {
        const user = await verifyEmailToken(body.data.token);
        const token = createAccessToken(user.id, user.email);
        return reply.code(200).send(authResponsePayload(user, token));
      } catch (err) {
        if (err instanceof AuthError) {
          return reply
            .code(err.statusCode as 400)
            .send({ detail: err.message });
        }
        throw err;
      }
    },
  );

  app.post(
    "/api/auth/resend-verification",
    {
      preHandler: requireAuth,
      schema: {
        tags: ["auth"],
        summary: "Resend email verification letter",
        security: [...bearerSecurity],
        response: {
          204: { type: "null" },
          400: ref("ErrorDetail"),
          429: ref("ErrorDetail"),
        },
      },
    },
    async (request, reply) => {
      try {
        await resendEmailVerification(request.user!.id);
        return reply.code(204).send();
      } catch (err) {
        if (err instanceof AuthError) {
          const code = err.statusCode === 429 ? 429 : 400;
          return reply.code(code).send({ detail: err.message });
        }
        throw err;
      }
    },
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
      const queryFrontend =
        typeof request.query === "object" &&
        request.query !== null &&
        "frontend" in request.query
          ? String((request.query as { frontend?: string }).frontend ?? "")
          : "";
      const frontendUrl = resolveFrontendUrl(
        queryFrontend || inferFrontendOrigin(request.headers.referer),
        undefined,
      );
      try {
        const { url, state, redirectUri } = buildGoogleAuthorizeUrl(frontendUrl);
        const cookies = oauthCookieNames();
        const cookieDomain = oauthCookieDomain(frontendUrl);
        const cookieOpts = {
          path: "/",
          httpOnly: true,
          sameSite: "lax" as const,
          maxAge: 600,
          secure: oauthCookieSecure(frontendUrl),
          signed: false,
          ...(cookieDomain ? { domain: cookieDomain } : {}),
        };
        reply
          .setCookie(cookies.state, state, cookieOpts)
          .setCookie(cookies.frontend, frontendUrl, cookieOpts)
          .setCookie(cookies.redirect, redirectUri, cookieOpts);
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
      const frontendForError = resolveFrontendUrl(
        query.frontend,
        request.cookies?.[cookies.frontend],
      );
      const clearOAuthCookies = () => {
        const clearOpts = { path: "/" as const };
        const domain = oauthCookieDomain(frontendForError);
        const domainOpts = domain ? { ...clearOpts, domain } : clearOpts;
        reply
          .clearCookie(cookies.state, clearOpts)
          .clearCookie(cookies.frontend, clearOpts)
          .clearCookie(cookies.redirect, clearOpts)
          .clearCookie(cookies.state, domainOpts)
          .clearCookie(cookies.frontend, domainOpts)
          .clearCookie(cookies.redirect, domainOpts);
      };
      if (!verifyOAuthState(query.state) || query.state !== cookieState) {
        request.log.warn(
          {
            hasCookieState: Boolean(cookieState),
            stateValid: verifyOAuthState(query.state),
          },
          "Google OAuth state mismatch",
        );
        clearOAuthCookies();
        return reply.redirect(oauthLoginErrorUrl(frontendForError, "oauth_state"));
      }
      if (!query.code) {
        clearOAuthCookies();
        return reply.redirect(oauthLoginErrorUrl(frontendForError, "oauth_denied"));
      }
      try {
        const frontend = resolveFrontendUrl(
          query.frontend,
          request.cookies?.[cookies.frontend],
        );
        const redirectUri = resolveOAuthRedirectUri(
          request.cookies?.[cookies.redirect],
          frontend,
        );
        const profile = await exchangeGoogleCode(
          query.code,
          redirectUri,
          (message, extra) => request.log.warn(extra ?? {}, message),
        );
        const { token, user, isNewUser } = await loginOrLinkGoogle({
          googleSub: profile.sub,
          email: profile.email,
        });
        if (isNewUser) {
          await recordUserRegister(user.id, { method: "google" });
        }
        try {
          await recordUserLogin(user.id, { method: "google" });
        } catch (auditErr) {
          request.log.warn({ err: auditErr }, "Google OAuth login audit failed");
        }
        const cookieDomain = oauthCookieDomain(frontend);
        const clearOpts = { path: "/" as const };
        const domainOpts = cookieDomain
          ? { ...clearOpts, domain: cookieDomain }
          : clearOpts;
        const claimedTripId = await claimGuestSessionForUser(
          request,
          reply,
          user.id,
        );
        reply
          .clearCookie(cookies.state, clearOpts)
          .clearCookie(cookies.frontend, clearOpts)
          .clearCookie(cookies.redirect, clearOpts)
          .clearCookie(cookies.state, domainOpts)
          .clearCookie(cookies.frontend, domainOpts)
          .clearCookie(cookies.redirect, domainOpts);
        const tripParam =
          claimedTripId != null ? `&trip=${claimedTripId}` : "";
        const redirectUrl =
          `${frontend}/auth/callback?token=${encodeURIComponent(token)}${tripParam}`;
        return reply.redirect(redirectUrl);
      } catch (err) {
        const frontend = resolveFrontendUrl(
          query.frontend,
          request.cookies?.[cookies.frontend],
        );
        if (err instanceof AuthError) {
          request.log.warn(
            { statusCode: err.statusCode, message: err.message },
            "Google OAuth callback rejected",
          );
          return reply.redirect(oauthLoginErrorUrl(frontend, "oauth_failed"));
        }
        request.log.error({ err }, "Google OAuth callback failed");
        return reply.redirect(oauthLoginErrorUrl(frontend, "oauth_failed"));
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
