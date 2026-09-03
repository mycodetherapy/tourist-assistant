import type { FastifyInstance, FastifyReply } from "fastify";
import { randomUUID } from "node:crypto";
import { z } from "zod";
import {
  mergeTripPreferences,
  normalizeTripPreferences,
  routeAnchorSchema,
} from "../lib/preferences.js";
import {
  InputValidationError,
  sanitizeAndValidate,
} from "../lib/inputValidation.js";
import { normalizePoiFactCacheKey } from "../lib/poiFactCacheKey.js";
import { enqueuePoiFact } from "../jobs/enqueue.js";
import * as poiFactsRepo from "../repos/poiFacts.js";
import { feedbackSchema, setItemFeedback } from "../services/itemFeedback.js";
import {
  createTripBodySchema,
  geocodeBodySchema,
  startRunBodySchema,
} from "../openapi/components.js";
import { recordAuditEvent } from "../repos/audit.js";
import * as tripsRepo from "../repos/trips.js";
import {
  incrementGuestFullRuns,
  incrementGuestPartialRuns,
  setGuestSessionTrip,
} from "../repos/guestSessions.js";
import { buildProgramView } from "../services/programView.js";
import { recoverCityFactIfNeeded } from "../services/cityFactRecovery.js";
import { repairProgramForTrip } from "../services/repairProgram.js";
import {
  geocodePlaces,
  resolveCityCenter,
  reverseGeocodeLabel,
} from "../services/geocode.js";
import {
  assertGuestCanCreateTrip,
  assertGuestCanStartRun,
  GuestRegisterRequiredError,
  GUEST_FULL_RUN_LIMIT,
  GUEST_PARTIAL_RUN_LIMIT,
} from "../services/guestQuotas.js";
import {
  checkAndConsumeGuestGeocodeQuota,
  GuestGeocodeQuotaError,
} from "../services/guestGeocodeQuotas.js";
import {
  ensureGuestSession,
  loadGuestSession,
  type GuestContext,
} from "../services/guestSession.js";
import { startRun, getRunStatus } from "../services/runManager.js";
import { tripBelongsToUser } from "../repos/trips.js";
import {
  assertGuestCaptcha,
  SmartCaptchaError,
  smartCaptchaConfigured,
} from "../services/smartCaptcha.js";

const createTripSchema = createTripBodySchema.extend({
  captcha_token: z.string().min(1).optional(),
});
const startRunSchema = startRunBodySchema.extend({
  captcha_token: z.string().min(1).optional(),
});
const geocodeSchema = geocodeBodySchema;

const reverseGeocodeSchema = z.object({
  lat: z.number().min(-90).max(90),
  lon: z.number().min(-180).max(180),
  city_hint: z.string().max(128).default(""),
});

const updatePrefsSchema = z
  .object({
    travel_party: z
      .enum([
        "solo",
        "couple",
        "family",
        "friends",
        "parent_child",
        "family_two",
      ])
      .optional(),
    route_anchor: routeAnchorSchema.nullable().optional(),
  })
  .refine((v) => Object.keys(v).length > 0, {
    message: "Нет полей для обновления",
  });

const poiFactStartSchema = z.object({
  poi_id: z.string().max(128).optional().nullable(),
  name: z.string().min(1).max(256),
});

function registerRequiredReply(reply: FastifyReply, err: GuestRegisterRequiredError) {
  return reply.code(403).send({
    detail: { code: err.code, message: err.message },
  });
}

function validationErrorReply(reply: FastifyReply, err: InputValidationError) {
  return reply.code(400).send({ detail: err.message });
}

async function requireGuestTrip(
  ctx: GuestContext,
  tripId: number,
): Promise<boolean> {
  if (ctx.session.trip_id !== tripId) {
    return false;
  }
  return tripBelongsToUser(tripId, ctx.userId);
}

function sessionView(ctx: GuestContext) {
  return {
    trip_id: ctx.session.trip_id,
    full_runs_used: ctx.session.full_runs_used,
    partial_runs_used: ctx.session.partial_runs_used,
    full_runs_limit: GUEST_FULL_RUN_LIMIT,
    partial_runs_limit: GUEST_PARTIAL_RUN_LIMIT,
    expires_at: ctx.session.expires_at,
  };
}

function geocodeQuotaReply(reply: FastifyReply, err: GuestGeocodeQuotaError) {
  return reply.code(429).send({
    detail: { code: "guest_geocode_quota_exceeded", message: err.message },
  });
}

function captchaReply(reply: FastifyReply, err: SmartCaptchaError) {
  const status =
    err.code === "captcha_required"
      ? 400
      : err.code === "captcha_unavailable"
        ? 503
        : 403;
  return reply.code(status).send({
    detail: { code: err.code, message: err.message },
  });
}

async function verifyGuestCaptchaRequest(
  request: Parameters<typeof assertGuestCaptcha>[0],
  reply: FastifyReply,
  token: string | undefined,
): Promise<boolean> {
  try {
    await assertGuestCaptcha(request, token);
    return true;
  } catch (err) {
    if (err instanceof SmartCaptchaError) {
      captchaReply(reply, err);
      return false;
    }
    throw err;
  }
}

async function consumeGuestGeocodeQuota(
  ctx: GuestContext,
  reply: FastifyReply,
): Promise<boolean> {
  try {
    await checkAndConsumeGuestGeocodeQuota(ctx.session.id);
    return true;
  } catch (err) {
    if (err instanceof GuestGeocodeQuotaError) {
      geocodeQuotaReply(reply, err);
      return false;
    }
    throw err;
  }
}

export async function registerGuestRoutes(app: FastifyInstance): Promise<void> {
  app.get("/api/guest/captcha-config", async () => ({
    smart_captcha_enabled: smartCaptchaConfigured(),
  }));

  app.post("/api/guest/session", async (request, reply) => {
    const ctx = await ensureGuestSession(request, reply);
    return sessionView(ctx);
  });

  app.get("/api/guest/session", async (request, reply) => {
    const ctx = await loadGuestSession(request);
    if (!ctx) {
      return reply.code(404).send({ detail: "Гостевая сессия не найдена" });
    }
    return sessionView(ctx);
  });

  app.post("/api/guest/trips/geocode", async (request, reply) => {
    const ctx = await ensureGuestSession(request, reply);
    if (!(await consumeGuestGeocodeQuota(ctx, reply))) return;
    const body = geocodeSchema.safeParse(request.body);
    if (!body.success) {
      return reply.code(400).send({ detail: "Некорректные данные" });
    }
    const results = await geocodePlaces(
      body.data.query.trim(),
      body.data.city_hint.trim(),
    );
    return { results };
  });

  app.post("/api/guest/trips/reverse-geocode", async (request, reply) => {
    const ctx = await ensureGuestSession(request, reply);
    if (!(await consumeGuestGeocodeQuota(ctx, reply))) return;
    const body = reverseGeocodeSchema.safeParse(request.body);
    if (!body.success) {
      return reply.code(400).send({ detail: "Некорректные данные" });
    }
    let label = await reverseGeocodeLabel(
      body.data.lat,
      body.data.lon,
      body.data.city_hint.trim(),
    );
    if (!label) {
      label = `${body.data.lat.toFixed(5)}, ${body.data.lon.toFixed(5)}`;
    }
    return { lat: body.data.lat, lon: body.data.lon, label };
  });

  app.post("/api/guest/trips", async (request, reply) => {
    const ctx = await ensureGuestSession(request, reply);
    const body = createTripSchema.safeParse(request.body);
    if (!body.success) {
      return reply.code(400).send({ detail: "Некорректные данные" });
    }
    if (!(await verifyGuestCaptchaRequest(request, reply, body.data.captcha_token))) {
      return;
    }
    try {
      assertGuestCanCreateTrip(ctx.session);
    } catch (err) {
      if (err instanceof GuestRegisterRequiredError) {
        return registerRequiredReply(reply, err);
      }
      throw err;
    }

    const rawPrefs = {
      ...(body.data.preferences ?? {}),
      route_anchor: body.data.route_anchor ?? null,
    };
    const preferences = normalizeTripPreferences(rawPrefs);
    let city: string;
    let userQuery: string;
    try {
      city = sanitizeAndValidate(body.data.city, "city");
      userQuery = sanitizeAndValidate(body.data.user_query, "message");
    } catch (err) {
      if (err instanceof InputValidationError) {
        return validationErrorReply(reply, err);
      }
      throw err;
    }

    const tripId = await tripsRepo.createTrip({
      userId: ctx.userId,
      city,
      dates: "Без дат",
      originCity: city,
      userQuery,
    });
    await tripsRepo.savePreferences(tripId, preferences);
    await setGuestSessionTrip(ctx.session.id, tripId);
    ctx.session.trip_id = tripId;

    await recordAuditEvent({
      action: "trip.create",
      entityType: "trip",
      entityId: String(tripId),
      userId: ctx.userId,
      metadata: { city, guest: true },
    });

    let runId: string | null = null;
    if (body.data.start_run !== false) {
      try {
        runId = await startRun(tripId, "full", { skipFreeQuota: true });
        await incrementGuestFullRuns(ctx.session.id);
      } catch (err) {
        if (err instanceof Error && /сборк|маршрут/i.test(err.message)) {
          return reply.code(409).send({
            detail: { code: "active_run", message: err.message },
          });
        }
        throw err;
      }
    }

    return reply.code(201).send({ trip_id: tripId, run_id: runId });
  });

  app.get<{ Params: { trip_id: string } }>(
    "/api/guest/trips/:trip_id",
    async (request, reply) => {
      const ctx = await loadGuestSession(request);
      if (!ctx) {
        return reply.code(401).send({ detail: "Гостевая сессия не найдена" });
      }
      const tripId = Number(request.params.trip_id);
      if (!(await requireGuestTrip(ctx, tripId))) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const trip = await tripsRepo.getTrip(tripId, ctx.userId);
      if (!trip) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      return {
        id: trip.id,
        city: trip.city,
        user_query: trip.user_query,
        created_at: trip.created_at,
        updated_at: trip.updated_at,
      };
    },
  );

  app.get<{ Params: { trip_id: string } }>(
    "/api/guest/trips/:trip_id/program",
    async (request, reply) => {
      const ctx = await loadGuestSession(request);
      if (!ctx) {
        return reply.code(401).send({ detail: "Гостевая сессия не найдена" });
      }
      const tripId = Number(request.params.trip_id);
      if (!(await requireGuestTrip(ctx, tripId))) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const trip = await tripsRepo.getTrip(tripId, ctx.userId);
      if (!trip) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const latest = await tripsRepo.getLatestItinerary(tripId);
      if (!latest) {
        return reply.code(404).send({ detail: "Программа не найдена" });
      }
      const repaired = await repairProgramForTrip(tripId, trip, latest.program);
      const program = await recoverCityFactIfNeeded({
        tripId,
        userId: ctx.userId,
        city: trip.city,
        versionId: latest.id,
        program: repaired,
      });
      return buildProgramView(tripId, { ...latest, program });
    },
  );

  app.put<{ Params: { trip_id: string } }>(
    "/api/guest/trips/:trip_id/preferences",
    async (request, reply) => {
      const ctx = await loadGuestSession(request);
      if (!ctx) {
        return reply.code(401).send({ detail: "Гостевая сессия не найдена" });
      }
      const tripId = Number(request.params.trip_id);
      if (!(await requireGuestTrip(ctx, tripId))) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const body = updatePrefsSchema.safeParse(request.body);
      if (!body.success) {
        return reply
          .code(400)
          .send({ detail: body.error.errors[0]?.message ?? "Некорректные данные" });
      }
      const existing = await tripsRepo.getPreferences(tripId);
      const merged = mergeTripPreferences(existing, body.data);
      await tripsRepo.savePreferences(tripId, merged);
      return merged;
    },
  );

  app.get<{ Params: { trip_id: string } }>(
    "/api/guest/trips/:trip_id/preferences",
    async (request, reply) => {
      const ctx = await loadGuestSession(request);
      if (!ctx) {
        return reply.code(401).send({ detail: "Гостевая сессия не найдена" });
      }
      const tripId = Number(request.params.trip_id);
      if (!(await requireGuestTrip(ctx, tripId))) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const prefs = await tripsRepo.getPreferences(tripId);
      return prefs ? normalizeTripPreferences(prefs) : null;
    },
  );

  app.get<{ Params: { trip_id: string } }>(
    "/api/guest/trips/:trip_id/city-center",
    async (request, reply) => {
      const ctx = await loadGuestSession(request);
      if (!ctx) {
        return reply.code(401).send({ detail: "Гостевая сессия не найдена" });
      }
      const tripId = Number(request.params.trip_id);
      if (!(await requireGuestTrip(ctx, tripId))) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const trip = await tripsRepo.getTrip(tripId, ctx.userId);
      if (!trip) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const center = await resolveCityCenter(trip.city);
      if (!center) {
        return reply
          .code(404)
          .send({ detail: `Не удалось определить центр города: ${trip.city}` });
      }
      return center;
    },
  );

  app.post<{ Params: { trip_id: string } }>(
    "/api/guest/trips/:trip_id/geocode",
    async (request, reply) => {
      const ctx = await loadGuestSession(request);
      if (!ctx) {
        return reply.code(401).send({ detail: "Гостевая сессия не найдена" });
      }
      const tripId = Number(request.params.trip_id);
      if (!(await requireGuestTrip(ctx, tripId))) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const trip = await tripsRepo.getTrip(tripId, ctx.userId);
      if (!trip) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      if (!(await consumeGuestGeocodeQuota(ctx, reply))) return;
      const body = geocodeSchema.safeParse(request.body);
      if (!body.success) {
        return reply.code(400).send({ detail: "Некорректные данные" });
      }
      const cityHint = (body.data.city_hint || trip.city).trim();
      const results = await geocodePlaces(body.data.query.trim(), cityHint);
      return { results };
    },
  );

  app.post<{ Params: { trip_id: string } }>(
    "/api/guest/trips/:trip_id/reverse-geocode",
    async (request, reply) => {
      const ctx = await loadGuestSession(request);
      if (!ctx) {
        return reply.code(401).send({ detail: "Гостевая сессия не найдена" });
      }
      const tripId = Number(request.params.trip_id);
      if (!(await requireGuestTrip(ctx, tripId))) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const trip = await tripsRepo.getTrip(tripId, ctx.userId);
      if (!trip) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      if (!(await consumeGuestGeocodeQuota(ctx, reply))) return;
      const body = reverseGeocodeSchema.safeParse(request.body);
      if (!body.success) {
        return reply.code(400).send({ detail: "Некорректные данные" });
      }
      const cityHint = (body.data.city_hint || trip.city).trim();
      let label = await reverseGeocodeLabel(
        body.data.lat,
        body.data.lon,
        cityHint,
      );
      if (!label) {
        label = `${body.data.lat.toFixed(5)}, ${body.data.lon.toFixed(5)}`;
      }
      return { lat: body.data.lat, lon: body.data.lon, label };
    },
  );

  app.post<{ Params: { trip_id: string } }>(
    "/api/guest/trips/:trip_id/runs",
    async (request, reply) => {
      const ctx = await loadGuestSession(request);
      if (!ctx) {
        return reply.code(401).send({ detail: "Гостевая сессия не найдена" });
      }
      const tripId = Number(request.params.trip_id);
      if (!(await requireGuestTrip(ctx, tripId))) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const body = startRunSchema.safeParse(request.body ?? {});
      if (!body.success) {
        return reply.code(400).send({ detail: "Некорректные данные" });
      }
      if (!(await verifyGuestCaptchaRequest(request, reply, body.data.captcha_token))) {
        return;
      }
      try {
        assertGuestCanStartRun(ctx.session, body.data.scope);
      } catch (err) {
        if (err instanceof GuestRegisterRequiredError) {
          return registerRequiredReply(reply, err);
        }
        throw err;
      }
      try {
        const runId = await startRun(tripId, body.data.scope, {
          skipFreeQuota: true,
        });
        if (body.data.scope === "full") {
          await incrementGuestFullRuns(ctx.session.id);
        } else {
          await incrementGuestPartialRuns(ctx.session.id);
        }
        return { trip_id: tripId, run_id: runId };
      } catch (err) {
        if (err instanceof Error && /сборк|маршрут/i.test(err.message)) {
          return reply.code(409).send({
            detail: { code: "active_run", message: err.message },
          });
        }
        throw err;
      }
    },
  );

  app.get<{ Params: { run_id: string } }>(
    "/api/guest/runs/:run_id",
    async (request, reply) => {
      const ctx = await loadGuestSession(request);
      if (!ctx) {
        return reply.code(401).send({ detail: "Гостевая сессия не найдена" });
      }
      const record = await getRunStatus(request.params.run_id);
      if (!record) {
        return reply.code(404).send({ detail: "Прогон не найден" });
      }
      if (!(await requireGuestTrip(ctx, record.trip_id))) {
        return reply.code(404).send({ detail: "Прогон не найден" });
      }
      return {
        run_id: record.run_id,
        trip_id: record.trip_id,
        status: record.status,
        error: record.error,
        version_id: record.version_id,
        city_fact_status: record.city_fact_status,
      };
    },
  );

  app.put<{ Params: { trip_id: string } }>(
    "/api/guest/trips/:trip_id/program/feedback",
    async (request, reply) => {
      const ctx = await loadGuestSession(request);
      if (!ctx) {
        return reply.code(401).send({ detail: "Гостевая сессия не найдена" });
      }
      const tripId = Number(request.params.trip_id);
      if (!(await requireGuestTrip(ctx, tripId))) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const trip = await tripsRepo.getTrip(tripId, ctx.userId);
      if (!trip) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const body = feedbackSchema.safeParse(request.body);
      if (!body.success) {
        return reply.code(400).send({ detail: body.error.errors[0]?.message });
      }
      try {
        await setItemFeedback(tripId, body.data);
      } catch (err) {
        return reply
          .code(400)
          .send({ detail: err instanceof Error ? err.message : String(err) });
      }
      const latest = await tripsRepo.getLatestItinerary(tripId);
      if (!latest) {
        return reply.code(404).send({ detail: "Программа не найдена" });
      }
      const repaired = await repairProgramForTrip(tripId, trip, latest.program);
      return buildProgramView(tripId, { ...latest, program: repaired });
    },
  );

  app.post<{ Params: { trip_id: string } }>(
    "/api/guest/trips/:trip_id/poi-facts",
    async (request, reply) => {
      const ctx = await loadGuestSession(request);
      if (!ctx) {
        return reply.code(401).send({ detail: "Гостевая сессия не найдена" });
      }
      const tripId = Number(request.params.trip_id);
      if (!(await requireGuestTrip(ctx, tripId))) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const trip = await tripsRepo.getTrip(tripId, ctx.userId);
      if (!trip) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const body = poiFactStartSchema.safeParse(request.body ?? {});
      if (!body.success) {
        return reply.code(400).send({ detail: "Некорректные данные" });
      }
      const poiId = (body.data.poi_id ?? "").trim();
      const name = body.data.name.trim();
      const cacheKey = normalizePoiFactCacheKey({
        poiId: poiId || null,
        name,
        city: trip.city,
      });

      const existing = await poiFactsRepo.getPoiFact(cacheKey);
      if (
        existing?.status === "ready" &&
        existing.text &&
        !poiFactsRepo.looksLikeSearchGarbage(existing.text) &&
        !poiFactsRepo.wikipediaSnippetIsStale(existing)
      ) {
        return poiFactsRepo.toPoiFactResponse(existing);
      }
      if (
        existing?.status === "pending" &&
        !poiFactsRepo.isPendingStale(existing.updated_at)
      ) {
        return poiFactsRepo.toPoiFactResponse(existing);
      }

      const sourceKind = poiId
        ? poiId.startsWith("Q") || poiId.startsWith("wikidata_")
          ? "wikidata"
          : /^osm_/.test(poiId)
            ? "osm"
            : "search"
        : "search";

      const row = await poiFactsRepo.upsertPoiFactPending({
        cacheKey,
        poiName: name,
        city: trip.city,
        sourceKind,
      });

      await enqueuePoiFact(randomUUID(), {
        trip_id: tripId,
        user_id: ctx.userId,
        city: trip.city,
        cache_key: cacheKey,
        poi_id: poiId,
        name,
      });

      return poiFactsRepo.toPoiFactResponse(row);
    },
  );

  app.get<{ Params: { trip_id: string; cache_key: string } }>(
    "/api/guest/trips/:trip_id/poi-facts/:cache_key",
    async (request, reply) => {
      const ctx = await loadGuestSession(request);
      if (!ctx) {
        return reply.code(401).send({ detail: "Гостевая сессия не найдена" });
      }
      const tripId = Number(request.params.trip_id);
      if (!(await requireGuestTrip(ctx, tripId))) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const cacheKey = decodeURIComponent(request.params.cache_key).trim();
      if (!cacheKey) {
        return reply.code(400).send({ detail: "Некорректный cache_key" });
      }
      const row = await poiFactsRepo.getPoiFact(cacheKey);
      if (!row) {
        return reply.code(404).send({ detail: "Справка не найдена" });
      }
      if (
        row.status === "ready" &&
        row.text &&
        poiFactsRepo.looksLikeSearchGarbage(row.text)
      ) {
        return {
          cache_key: row.cache_key,
          name: row.poi_name,
          status: "failed" as const,
          text: null,
          error: poiFactsRepo.POI_FACT_NOT_FOUND,
        };
      }
      return poiFactsRepo.toPoiFactResponse(row);
    },
  );
}
