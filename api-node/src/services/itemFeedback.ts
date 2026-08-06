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

const MAX_LIKED_ROUTES = 10;
const MAX_LIKED_ROUTE_STOPS = 40;

export const feedbackSchema = z
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
