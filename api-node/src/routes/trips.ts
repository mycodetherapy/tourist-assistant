import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { requireAuth } from "../middleware/auth.js";
import {
  mergeTripPreferences,
  normalizeTripPreferences,
  routeAnchorSchema,
} from "../lib/preferences.js";
import {
  makeItemKey,
  makeRouteStopKey,
  parseRouteStopKey,
} from "../lib/itemKey.js";
import {
  AuthError,
  requireUserLlmConfigured,
} from "../services/auth.js";
import { RunQuotaError } from "../services/quotas.js";
import {
  hasActiveRunForTrip,
  startRun,
} from "../services/runManager.js";
import { buildProgramView } from "../services/programView.js";
import {
  collectRouteStopPoiIds,
  parseNumberedSection,
  parseRoutesSection,
} from "../services/parseProgram.js";
import {
  geocodePlaces,
  resolveCityCenter,
  reverseGeocodeLabel,
} from "../services/geocode.js";
import { recordAuditEvent } from "../repos/audit.js";
import { saveUserProfile } from "../repos/users.js";
import * as tripsRepo from "../repos/trips.js";

const MAX_LIKED_ROUTES = 3;
const MAX_LIKED_ROUTE_STOPS = 10;

const createTripSchema = z.object({
  city: z.string().min(1),
  route_anchor: routeAnchorSchema.nullable().optional(),
  user_query: z.string().default("Составь три варианта маршрута по городу"),
  preferences: z.record(z.unknown()).nullable().optional(),
  start_run: z.boolean().default(true),
});

const startRunSchema = z.object({
  scope: z.enum(["routes", "full"]).default("routes"),
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

const geocodeSchema = z.object({
  query: z.string().min(2).max(500),
  city_hint: z.string().max(128).default(""),
});

const reverseGeocodeSchema = z.object({
  lat: z.number().min(-90).max(90),
  lon: z.number().min(-180).max(180),
  city_hint: z.string().max(128).default(""),
});

const feedbackSchema = z
  .object({
    version_id: z.number().nullable().optional(),
    section: z.enum(["routes", "route_stops"]),
    item_key: z.string().nullable().optional(),
    item_index: z.number().int().min(0).nullable().optional(),
    vote: z.union([z.literal(1), z.literal(-1)]).nullable(),
  })
  .refine((v) => (v.item_key ?? "").trim() || v.item_index !== undefined, {
    message: "Укажите item_key или item_index",
  });

function sanitizeCity(value: string): string {
  return value.trim().slice(0, 500);
}

function sanitizeMessage(value: string): string {
  return value.trim().slice(0, 2000);
}

export async function registerTripsRoutes(app: FastifyInstance): Promise<void> {
  app.get(
    "/api/trips",
    { preHandler: requireAuth },
    async (request) => {
      const rows = await tripsRepo.listTrips(request.user!.id);
      return rows;
    },
  );

  app.post(
    "/api/trips/geocode",
    { preHandler: requireAuth },
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
    { preHandler: requireAuth },
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
          await requireUserLlmConfigured(request.user!.id);
        } catch (err) {
          if (err instanceof AuthError) {
            return reply.code(err.statusCode).send({
              detail: { code: "llm_key_required", message: err.message },
            });
          }
          throw err;
        }
      }
      const city = sanitizeCity(body.data.city);
      const tripId = await tripsRepo.createTrip({
        userId: request.user!.id,
        city,
        dates: "Без дат",
        originCity: city,
        userQuery: sanitizeMessage(body.data.user_query),
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
      return buildProgramView(tripId, latest);
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
    { preHandler: requireAuth },
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
        await requireUserLlmConfigured(request.user!.id);
        const runId = await startRun(tripId, body.data.scope);
        return { trip_id: tripId, run_id: runId };
      } catch (err) {
        if (err instanceof AuthError) {
          return reply.code(err.statusCode).send({
            detail: { code: "llm_key_required", message: err.message },
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
      return buildProgramView(tripId, latest);
    },
  );
}

async function setItemFeedback(
  tripId: number,
  body: z.infer<typeof feedbackSchema>,
): Promise<void> {
  const latest = await tripsRepo.getLatestItinerary(tripId);
  if (!latest) throw new Error("Программа не найдена");
  if (
    body.version_id != null &&
    !(await tripsRepo.getItineraryVersion(tripId, body.version_id))
  ) {
    throw new Error("Версия программы не найдена");
  }

  const program = latest.program;
  let resolvedKey: string | null = null;
  let matchedIndex: number | null = null;

  if (body.section === "route_stops") {
    const poiLabels = collectRouteStopPoiIds(program);
    const poiIds = Object.keys(poiLabels);
    const normalizedKey = (body.item_key ?? "").trim();
    let poiId: string | null = null;
    if (normalizedKey.startsWith("poi:")) {
      poiId = parseRouteStopKey(normalizedKey);
    } else if (
      body.item_index != null &&
      body.item_index >= 0 &&
      body.item_index < poiIds.length
    ) {
      poiId = poiIds[body.item_index] ?? null;
    }
    if (poiId && poiLabels[poiId]) {
      matchedIndex = poiIds.indexOf(poiId);
      resolvedKey = makeRouteStopKey(poiId);
    }
  } else {
    const routesText = String(program.routes_text ?? "");
    const parsed = routesText
      ? parseRoutesSection(routesText)
      : parseNumberedSection(routesText);
    const normalizedKey = (body.item_key ?? "").trim();
    if (normalizedKey) {
      for (let i = 0; i < parsed.items.length; i++) {
        if (makeItemKey("routes", parsed.items[i]!) === normalizedKey) {
          matchedIndex = i;
          resolvedKey = normalizedKey;
          break;
        }
      }
    } else if (
      body.item_index != null &&
      body.item_index >= 0 &&
      body.item_index < parsed.items.length
    ) {
      matchedIndex = body.item_index;
      resolvedKey = makeItemKey("routes", parsed.items[body.item_index]!);
    }
  }

  if (matchedIndex === null || !resolvedKey) {
    throw new Error("Пункт подборки не найден");
  }

  const votes = await tripsRepo.listItemFeedback(tripId);
  if (body.vote === 1 && body.section === "routes") {
    const alreadyLiked = votes[resolvedKey] === 1;
    if (!alreadyLiked) {
      const liked = await tripsRepo.countLikedRoutes(tripId, program);
      if (liked >= MAX_LIKED_ROUTES) {
        throw new Error(
          `Лимит лайков маршрутов (${MAX_LIKED_ROUTES}) для поездки`,
        );
      }
    }
  }
  if (body.vote === 1 && body.section === "route_stops") {
    const alreadyLiked = votes[resolvedKey] === 1;
    if (!alreadyLiked) {
      const liked = await tripsRepo.countLikedRouteStops(tripId);
      if (liked >= MAX_LIKED_ROUTE_STOPS) {
        throw new Error(`Лимит лайков остановок (${MAX_LIKED_ROUTE_STOPS})`);
      }
    }
  }

  if (body.vote === null) {
    await tripsRepo.deleteItemFeedback(tripId, body.section, resolvedKey);
    await tripsRepo.deleteFeedbackAtIndex(tripId, body.section, matchedIndex);
    return;
  }

  await tripsRepo.deleteFeedbackAtIndex(
    tripId,
    body.section,
    matchedIndex,
    resolvedKey,
  );
  await tripsRepo.upsertItemFeedback({
    tripId,
    versionId: latest.id,
    section: body.section,
    itemIndex: matchedIndex,
    itemKey: resolvedKey,
    vote: body.vote,
  });
}
