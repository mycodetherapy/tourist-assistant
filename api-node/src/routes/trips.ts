import { randomUUID } from "node:crypto";
import type { FastifyInstance, FastifyReply } from "fastify";
import { z } from "zod";
import { requireAuth } from "../middleware/auth.js";
import {
  mergeTripPreferences,
  normalizeTripPreferences,
  routeAnchorSchema,
} from "../lib/preferences.js";
import {
  AuthError,
  assertCanStartRun,
} from "../services/auth.js";
import { feedbackSchema, setItemFeedback } from "../services/itemFeedback.js";
import { FreeRunQuotaError } from "../services/freeQuotas.js";
import { RunQuotaError } from "../services/quotas.js";
import {
  hasActiveRunForTrip,
  startRun,
} from "../services/runManager.js";
import { buildProgramView } from "../services/programView.js";
import { buildTripOsrmUpdateStatus } from "../services/osrmTripUpdate.js";
import { recoverCityFactIfNeeded } from "../services/cityFactRecovery.js";
import { repairProgramForTrip } from "../services/repairProgram.js";
import {
  geocodePlaces,
  resolveCityCenter,
  reverseGeocodeLabel,
} from "../services/geocode.js";
import { recordAuditEvent } from "../repos/audit.js";
import { saveUserProfile } from "../repos/users.js";
import {
  bearerSecurity,
  createTripBodySchema,
  geocodeBodySchema,
  ref,
  startRunBodySchema,
} from "../openapi/components.js";

import * as tripsRepo from "../repos/trips.js";
import {
  InputValidationError,
  sanitizeAndValidate,
} from "../lib/inputValidation.js";
import { normalizePoiFactCacheKey } from "../lib/poiFactCacheKey.js";
import { enqueuePoiFact } from "../jobs/enqueue.js";
import * as poiFactsRepo from "../repos/poiFacts.js";

const startRunSchema = startRunBodySchema;
const createTripSchema = createTripBodySchema;

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

const geocodeSchema = geocodeBodySchema;

const reverseGeocodeSchema = z.object({
  lat: z.number().min(-90).max(90),
  lon: z.number().min(-180).max(180),
  city_hint: z.string().max(128).default(""),
});

const poiFactStartSchema = z.object({
  poi_id: z.string().max(128).optional().nullable(),
  name: z.string().min(1).max(256),
});

function validationErrorReply(reply: FastifyReply, err: InputValidationError) {
  return reply.code(400).send({ detail: err.message });
}

export async function registerTripsRoutes(app: FastifyInstance): Promise<void> {
  app.get(
    "/api/trips",
    {
      preHandler: requireAuth,
      schema: {
        tags: ["trips"],
        summary: "List trips",
        security: [...bearerSecurity],
        response: {
          200: { type: "array", items: ref("TripSummary") },
        },
      },
    },
    async (request) => {
      const rows = await tripsRepo.listTrips(request.user!.id);
      return rows;
    },
  );

  app.post(
    "/api/trips/geocode",
    {
      preHandler: requireAuth,
      schema: {
        tags: ["trips"],
        summary: "Geocode (new trip wizard)",
        security: [...bearerSecurity],
        body: ref("GeocodeRequest"),
      },
    },
    async (request, reply) => {
      const body = geocodeSchema.safeParse(request.body);
      if (!body.success) {
        return reply.code(400).send({ detail: "Некорректные данные" });
      }
      const results = await geocodePlaces(
        body.data.query.trim(),
        body.data.city_hint.trim(),
      );
      return { results };
    },
  );

  app.post(
    "/api/trips/reverse-geocode",
    { preHandler: requireAuth },
    async (request, reply) => {
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
    },
  );

  app.post(
    "/api/trips",
    {
      preHandler: requireAuth,
      schema: {
        tags: ["trips"],
        summary: "Create trip",
        security: [...bearerSecurity],
        body: ref("CreateTripRequest"),
        response: {
          201: ref("CreateTripResponse"),
          400: ref("ErrorDetail"),
          409: ref("ErrorDetail"),
          428: ref("ErrorDetail"),
          429: ref("ErrorDetail"),
          503: ref("ErrorDetail"),
        },
      },
    },
    async (request, reply) => {
      const body = createTripSchema.safeParse(request.body);
      if (!body.success) {
        return reply.code(400).send({ detail: "Некорректные данные" });
      }
      const rawPrefs = {
        ...(body.data.preferences ?? {}),
        route_anchor: body.data.route_anchor ?? null,
      };
      const preferences = normalizeTripPreferences(rawPrefs);
      if (body.data.start_run) {
        try {
          await assertCanStartRun(request.user!.id);
        } catch (err) {
          if (err instanceof AuthError) {
            const code =
              err.statusCode === 503 ? "ai_platform_unavailable" : "llm_key_required";
            const status = err.statusCode === 503 ? 503 : 428;
            return reply.code(status).send({
              detail: { code, message: err.message },
            });
          }
          throw err;
        }
      }
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
        userId: request.user!.id,
        city,
        dates: "Без дат",
        originCity: city,
        userQuery,
      });
      await tripsRepo.savePreferences(tripId, preferences);
      await saveUserProfile(request.user!.id, preferences);
      await recordAuditEvent({
        action: "trip.create",
        entityType: "trip",
        entityId: String(tripId),
        userId: request.user!.id,
        metadata: { city },
      });

      let runId: string | null = null;
      if (body.data.start_run) {
        try {
          runId = await startRun(tripId, "full");
        } catch (err) {
          if (err instanceof FreeRunQuotaError) {
            return reply.code(429).send({
              detail: { code: "free_run_quota_exceeded", message: err.message },
            });
          }
          if (err instanceof RunQuotaError) {
            return reply.code(429).send({
              detail: { code: "run_quota_exceeded", message: err.message },
            });
          }
          if (err instanceof Error && /сборк|маршрут/i.test(err.message)) {
            return reply.code(409).send({
              detail: { code: "active_run", message: err.message },
            });
          }
          throw err;
        }
      }
      return reply.code(201).send({ trip_id: tripId, run_id: runId });
    },
  );

  app.delete<{ Params: { trip_id: string } }>(
    "/api/trips/:trip_id",
    { preHandler: requireAuth },
    async (request, reply) => {
      const tripId = Number(request.params.trip_id);
      const trip = await tripsRepo.getTrip(tripId, request.user!.id);
      if (!trip) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      if (await hasActiveRunForTrip(tripId)) {
        return reply
          .code(409)
          .send({ detail: "Нельзя удалить поездку во время сборки программы" });
      }
      const ok = await tripsRepo.deleteTrip(tripId, request.user!.id);
      if (!ok) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      return reply.code(204).send();
    },
  );

  app.get<{ Params: { trip_id: string } }>(
    "/api/trips/:trip_id",
    { preHandler: requireAuth },
    async (request, reply) => {
      const trip = await tripsRepo.getTrip(
        Number(request.params.trip_id),
        request.user!.id,
      );
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
    "/api/trips/:trip_id/program",
    { preHandler: requireAuth },
    async (request, reply) => {
      const tripId = Number(request.params.trip_id);
      const trip = await tripsRepo.getTrip(tripId, request.user!.id);
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
        userId: request.user!.id,
        city: trip.city,
        versionId: latest.id,
        program: repaired,
      });
      return buildProgramView(tripId, { ...latest, program });
    },
  );

  app.get<{ Params: { trip_id: string } }>(
    "/api/trips/:trip_id/osrm-update",
    {
      preHandler: requireAuth,
      schema: {
        tags: ["trips"],
        summary: "Есть ли более новый OSRM-граф, чем последняя сборка маршрутов",
      },
    },
    async (request, reply) => {
      const tripId = Number(request.params.trip_id);
      const trip = await tripsRepo.getTrip(tripId, request.user!.id);
      if (!trip) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const latest = await tripsRepo.getLatestItinerary(tripId);
      return buildTripOsrmUpdateStatus({ city: trip.city, latest });
    },
  );

  app.put<{ Params: { trip_id: string } }>(
    "/api/trips/:trip_id/preferences",
    { preHandler: requireAuth },
    async (request, reply) => {
      const tripId = Number(request.params.trip_id);
      const trip = await tripsRepo.getTrip(tripId, request.user!.id);
      if (!trip) {
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
    "/api/trips/:trip_id/preferences",
    { preHandler: requireAuth },
    async (request, reply) => {
      const tripId = Number(request.params.trip_id);
      const trip = await tripsRepo.getTrip(tripId, request.user!.id);
      if (!trip) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const prefs = await tripsRepo.getPreferences(tripId);
      return prefs ? normalizeTripPreferences(prefs) : null;
    },
  );

  app.get<{ Params: { trip_id: string } }>(
    "/api/trips/:trip_id/city-center",
    { preHandler: requireAuth },
    async (request, reply) => {
      const trip = await tripsRepo.getTrip(
        Number(request.params.trip_id),
        request.user!.id,
      );
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
    "/api/trips/:trip_id/geocode",
    { preHandler: requireAuth },
    async (request, reply) => {
      const tripId = Number(request.params.trip_id);
      const trip = await tripsRepo.getTrip(tripId, request.user!.id);
      if (!trip) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
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
    "/api/trips/:trip_id/reverse-geocode",
    { preHandler: requireAuth },
    async (request, reply) => {
      const tripId = Number(request.params.trip_id);
      const trip = await tripsRepo.getTrip(tripId, request.user!.id);
      if (!trip) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
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
    "/api/trips/:trip_id/runs",
    {
      preHandler: requireAuth,
      schema: {
        tags: ["trips"],
        summary: "Start graph run",
        security: [...bearerSecurity],
        body: ref("StartRunRequest"),
      },
    },
    async (request, reply) => {
      const tripId = Number(request.params.trip_id);
      const trip = await tripsRepo.getTrip(tripId, request.user!.id);
      if (!trip) {
        return reply.code(404).send({ detail: "Поездка не найдена" });
      }
      const body = startRunSchema.safeParse(request.body ?? {});
      if (!body.success) {
        return reply.code(400).send({ detail: "Некорректные данные" });
      }
      try {
        await assertCanStartRun(request.user!.id);
        const runId = await startRun(tripId, body.data.scope);
        return { trip_id: tripId, run_id: runId };
      } catch (err) {
        if (err instanceof AuthError) {
          const code =
            err.statusCode === 503 ? "ai_platform_unavailable" : "llm_key_required";
          const status = err.statusCode === 503 ? 503 : 428;
          return reply.code(status).send({
            detail: { code, message: err.message },
          });
        }
        if (err instanceof FreeRunQuotaError) {
          return reply.code(429).send({
            detail: { code: "free_run_quota_exceeded", message: err.message },
          });
        }
        if (err instanceof RunQuotaError) {
          return reply.code(429).send({
            detail: { code: "run_quota_exceeded", message: err.message },
          });
        }
        if (err instanceof Error && /сборк|маршрут/i.test(err.message)) {
          return reply.code(409).send({
            detail: { code: "active_run", message: err.message },
          });
        }
        throw err;
      }
    },
  );

  app.put<{ Params: { trip_id: string } }>(
    "/api/trips/:trip_id/program/feedback",
    { preHandler: requireAuth },
    async (request, reply) => {
      const tripId = Number(request.params.trip_id);
      const trip = await tripsRepo.getTrip(tripId, request.user!.id);
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
    "/api/trips/:trip_id/poi-facts",
    { preHandler: requireAuth },
    async (request, reply) => {
      const tripId = Number(request.params.trip_id);
      const trip = await tripsRepo.getTrip(tripId, request.user!.id);
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
        !poiFactsRepo.looksLikeSearchGarbage(existing.text)
      ) {
        return poiFactsRepo.toPoiFactResponse(existing);
      }
      if (
        existing?.status === "pending" &&
        !poiFactsRepo.isPendingStale(existing.updated_at)
      ) {
        return poiFactsRepo.toPoiFactResponse(existing);
      }

      try {
        await assertCanStartRun(request.user!.id);
      } catch (err) {
        if (err instanceof AuthError) {
          const code =
            err.statusCode === 503 ? "ai_platform_unavailable" : "llm_key_required";
          const status = err.statusCode === 503 ? 503 : 428;
          return reply.code(status).send({
            detail: { code, message: err.message },
          });
        }
        throw err;
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
        user_id: request.user!.id,
        city: trip.city,
        cache_key: cacheKey,
        poi_id: poiId,
        name,
      });

      return poiFactsRepo.toPoiFactResponse(row);
    },
  );

  app.get<{ Params: { trip_id: string; cache_key: string } }>(
    "/api/trips/:trip_id/poi-facts/:cache_key",
    { preHandler: requireAuth },
    async (request, reply) => {
      const tripId = Number(request.params.trip_id);
      const trip = await tripsRepo.getTrip(tripId, request.user!.id);
      if (!trip) {
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
