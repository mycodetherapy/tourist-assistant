import { z } from "zod";
import {
  makeItemKey,
  makeRouteStopKey,
  parseRouteStopKey,
} from "../lib/itemKey.js";
import {
  collectRouteStopPoiIds,
  parseProgramRoutes,
} from "../services/parseProgram.js";
import * as tripsRepo from "../repos/trips.js";

const MAX_PINNED_ROUTES = 10;
const MAX_LIKED_ROUTE_STOPS = 40;
export const ROUTE_PINS_SECTION = "route_pins";
/** Совпадает с program/route_feedback.ROUTE_PINS_MIGRATED_KEY */
export const ROUTE_PINS_MIGRATED_KEY = "__route_pins_migrated__";

async function migrateLegacyRouteLikesToPins(
  tripId: number,
  program: Record<string, unknown>,
  versionId: number,
): Promise<void> {
  const pins = await tripsRepo.listItemFeedbackBySection(tripId, ROUTE_PINS_SECTION);
  if (pins[ROUTE_PINS_MIGRATED_KEY] === 1) return;
  const votes = await tripsRepo.listItemFeedback(tripId);
  const parsed = parseProgramRoutes(program);
  for (let i = 0; i < parsed.items.length; i++) {
    const routesKey = makeItemKey("routes", parsed.items[i]!);
    if (votes[routesKey] !== 1) continue;
    const pinKey = makeItemKey(ROUTE_PINS_SECTION, parsed.items[i]!);
    await tripsRepo.upsertItemFeedback({
      tripId,
      versionId,
      section: ROUTE_PINS_SECTION,
      itemIndex: i,
      itemKey: pinKey,
      vote: 1,
    });
  }
  await tripsRepo.upsertItemFeedback({
    tripId,
    versionId,
    section: ROUTE_PINS_SECTION,
    itemIndex: -1,
    itemKey: ROUTE_PINS_MIGRATED_KEY,
    vote: 1,
  });
}

async function clearRouteCasePreserved(
  versionId: number,
  program: Record<string, unknown>,
  caseIndex: number,
): Promise<void> {
  const routesRaw = program.routes;
  if (!routesRaw || typeof routesRaw !== "object" || Array.isArray(routesRaw)) {
    return;
  }
  const routes = routesRaw as {
    cases?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
  const cases = Array.isArray(routes.cases) ? [...routes.cases] : [];
  const current = cases[caseIndex];
  if (!current || !current.preserved) return;
  cases[caseIndex] = { ...current, preserved: false };
  await tripsRepo.patchItineraryProgram(versionId, {
    routes: { ...routes, cases },
  });
}

export const feedbackSchema = z
  .object({
    version_id: z.number().nullable().optional(),
    section: z.enum(["routes", "route_stops", "route_pins"]),
    item_key: z.string().nullable().optional(),
    item_index: z.number().int().min(0).nullable().optional(),
    vote: z.union([z.literal(1), z.literal(-1)]).nullable(),
  })
  .refine((v) => (v.item_key ?? "").trim() || v.item_index !== undefined, {
    message: "Укажите item_key или item_index",
  })
  .refine(
    (v) => v.section !== "route_pins" || v.vote === 1 || v.vote === null,
    { message: "Для закрепления допустимы только pin (1) или снятие (null)" },
  );

export async function setItemFeedback(
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
  if (body.section === ROUTE_PINS_SECTION || body.section === "routes") {
    await migrateLegacyRouteLikesToPins(tripId, program, latest.id);
  }
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
    const parsed = parseProgramRoutes(program);
    const keySection =
      body.section === ROUTE_PINS_SECTION ? ROUTE_PINS_SECTION : "routes";
    const normalizedKey = (body.item_key ?? "").trim();
    // UI передаёт routes-ключ; для pin пересчитываем.
    if (normalizedKey) {
      for (let i = 0; i < parsed.items.length; i++) {
        const routesKey = makeItemKey("routes", parsed.items[i]!);
        const sectionKey = makeItemKey(keySection, parsed.items[i]!);
        if (normalizedKey === routesKey || normalizedKey === sectionKey) {
          matchedIndex = i;
          resolvedKey = sectionKey;
          break;
        }
      }
    } else if (
      body.item_index != null &&
      body.item_index >= 0 &&
      body.item_index < parsed.items.length
    ) {
      matchedIndex = body.item_index;
      resolvedKey = makeItemKey(keySection, parsed.items[body.item_index]!);
    }
  }

  if (matchedIndex === null || !resolvedKey) {
    throw new Error("Пункт подборки не найден");
  }

  if (body.vote === 1 && body.section === ROUTE_PINS_SECTION) {
    const pinned = await tripsRepo.countPinnedRoutes(tripId, program);
    const already = await tripsRepo.hasRoutePin(tripId, resolvedKey);
    if (!already && pinned >= MAX_PINNED_ROUTES) {
      throw new Error(
        `Лимит сохранённых маршрутов (${MAX_PINNED_ROUTES}) для поездки`,
      );
    }
  }
  if (body.vote === 1 && body.section === "route_stops") {
    const votes = await tripsRepo.listItemFeedback(tripId);
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
    if (body.section === ROUTE_PINS_SECTION) {
      await clearRouteCasePreserved(latest.id, program, matchedIndex);
    }
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
