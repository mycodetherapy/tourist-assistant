import { query } from "../db/pool.js";

function toIso(value: Date | string): string {
  return value instanceof Date ? value.toISOString() : String(value);
}

export interface TripRow {
  id: number;
  user_id: number;
  city: string;
  dates: string;
  origin_city: string;
  user_query: string | null;
  created_at: string;
  updated_at: string;
}

export interface TripSummary {
  id: number;
  city: string;
  updated_at: string;
}

export interface ItineraryVersion {
  id: number;
  version: number;
  scope: string;
  program: Record<string, unknown>;
  approved: boolean;
  created_at: string;
}

export async function listTrips(
  userId: number,
  limit = 20,
): Promise<TripSummary[]> {
  const { rows } = await query<{ id: string; city: string; updated_at: Date }>(
    `SELECT id, city, updated_at FROM trips
     WHERE user_id = $1
     ORDER BY updated_at DESC
     LIMIT $2`,
    [userId, limit],
  );
  return rows.map((r) => ({
    id: Number(r.id),
    city: r.city,
    updated_at: toIso(r.updated_at),
  }));
}

export async function getTrip(
  tripId: number,
  userId?: number,
): Promise<TripRow | null> {
  const params: unknown[] = [tripId];
  let sql = `SELECT id, user_id, city, dates, origin_city, user_query, created_at, updated_at
             FROM trips WHERE id = $1`;
  if (userId !== undefined) {
    sql += ` AND user_id = $2`;
    params.push(userId);
  }
  const { rows } = await query<TripRow>(sql, params);
  const row = rows[0];
  if (!row) return null;
  return {
    ...row,
    id: Number(row.id),
    user_id: Number(row.user_id),
    created_at: toIso(row.created_at),
    updated_at: toIso(row.updated_at),
  };
}

export async function tripBelongsToUser(
  tripId: number,
  userId: number,
): Promise<boolean> {
  const trip = await getTrip(tripId, userId);
  return trip !== null;
}

export async function createTrip(params: {
  userId: number;
  city: string;
  dates: string;
  originCity: string;
  userQuery: string;
}): Promise<number> {
  const now = new Date();
  const { rows } = await query<{ id: string }>(
    `INSERT INTO trips (user_id, city, dates, origin_city, user_query, status, created_at, updated_at)
     VALUES ($1, $2, $3, $4, $5, 'active', $6, $6)
     RETURNING id`,
    [
      params.userId,
      params.city,
      params.dates,
      params.originCity,
      params.userQuery,
      now,
    ],
  );
  return Number(rows[0]!.id);
}

export async function deleteTrip(
  tripId: number,
  userId: number,
): Promise<boolean> {
  const { rowCount } = await query(
    `DELETE FROM trips WHERE id = $1 AND user_id = $2`,
    [tripId, userId],
  );
  return (rowCount ?? 0) > 0;
}

export async function savePreferences(
  tripId: number,
  preferences: Record<string, unknown>,
): Promise<void> {
  await query(
    `INSERT INTO trip_preferences (trip_id, preferences_json)
     VALUES ($1, $2::jsonb)
     ON CONFLICT (trip_id) DO UPDATE SET preferences_json = EXCLUDED.preferences_json`,
    [tripId, JSON.stringify(preferences)],
  );
}

export async function getPreferences(
  tripId: number,
): Promise<Record<string, unknown> | null> {
  const { rows } = await query<{ preferences_json: Record<string, unknown> }>(
    `SELECT preferences_json FROM trip_preferences WHERE trip_id = $1`,
    [tripId],
  );
  return rows[0]?.preferences_json ?? null;
}

export async function getLatestItinerary(
  tripId: number,
): Promise<ItineraryVersion | null> {
  const { rows } = await query<{
    id: string;
    version: number;
    scope: string;
    program_json: Record<string, unknown>;
    approved: boolean;
    created_at: Date;
  }>(
    `SELECT id, version, scope, program_json, approved, created_at
     FROM itinerary_versions
     WHERE trip_id = $1
     ORDER BY version DESC
     LIMIT 1`,
    [tripId],
  );
  const row = rows[0];
  if (!row) return null;
  return {
    id: Number(row.id),
    version: row.version,
    scope: row.scope,
    program: row.program_json,
    approved: row.approved,
    created_at: toIso(row.created_at),
  };
}

export async function getItineraryVersion(
  tripId: number,
  versionId: number,
): Promise<ItineraryVersion | null> {
  const { rows } = await query<{
    id: string;
    version: number;
    scope: string;
    program_json: Record<string, unknown>;
    approved: boolean;
    created_at: Date;
  }>(
    `SELECT id, version, scope, program_json, approved, created_at
     FROM itinerary_versions
     WHERE trip_id = $1 AND id = $2`,
    [tripId, versionId],
  );
  const row = rows[0];
  if (!row) return null;
  return {
    id: Number(row.id),
    version: row.version,
    scope: row.scope,
    program: row.program_json,
    approved: row.approved,
    created_at: toIso(row.created_at),
  };
}

export async function listItemFeedback(
  tripId: number,
): Promise<Record<string, number>> {
  const { rows } = await query<{ item_key: string; vote: number }>(
    `SELECT item_key, vote FROM program_item_feedback WHERE trip_id = $1`,
    [tripId],
  );
  const out: Record<string, number> = {};
  for (const r of rows) {
    out[r.item_key] = r.vote;
  }
  return out;
}

export async function deleteItemFeedback(
  tripId: number,
  section: string,
  itemKey: string,
): Promise<void> {
  await query(
    `DELETE FROM program_item_feedback
     WHERE trip_id = $1 AND section = $2 AND item_key = $3`,
    [tripId, section, itemKey],
  );
}

export async function deleteFeedbackAtIndex(
  tripId: number,
  section: string,
  itemIndex: number,
  exceptItemKey?: string,
): Promise<void> {
  if (exceptItemKey) {
    await query(
      `DELETE FROM program_item_feedback
       WHERE trip_id = $1 AND section = $2 AND item_index = $3 AND item_key <> $4`,
      [tripId, section, itemIndex, exceptItemKey],
    );
  } else {
    await query(
      `DELETE FROM program_item_feedback
       WHERE trip_id = $1 AND section = $2 AND item_index = $3`,
      [tripId, section, itemIndex],
    );
  }
}

export async function upsertItemFeedback(params: {
  tripId: number;
  versionId: number | null;
  section: string;
  itemIndex: number;
  itemKey: string;
  vote: number;
}): Promise<void> {
  const now = new Date();
  await query(
    `INSERT INTO program_item_feedback
       (trip_id, itinerary_version_id, section, item_index, item_key, vote, updated_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7)
     ON CONFLICT (trip_id, section, item_key) DO UPDATE SET
       itinerary_version_id = EXCLUDED.itinerary_version_id,
       item_index = EXCLUDED.item_index,
       vote = EXCLUDED.vote,
       updated_at = EXCLUDED.updated_at`,
    [
      params.tripId,
      params.versionId,
      params.section,
      params.itemIndex,
      params.itemKey,
      params.vote,
      now,
    ],
  );
}

export async function countLikedRouteStops(tripId: number): Promise<number> {
  const { rows } = await query<{ count: string }>(
    `SELECT COUNT(*)::text AS count FROM program_item_feedback
     WHERE trip_id = $1 AND section = 'route_stops' AND vote = 1`,
    [tripId],
  );
  return Number(rows[0]?.count ?? 0);
}

export async function countLikedRoutes(
  tripId: number,
  program: Record<string, unknown>,
): Promise<number> {
  const votes = await listItemFeedback(tripId);
  const routesText = String(program.routes_text ?? "");
  if (!routesText.trim()) return 0;
  const { parseRoutesSection } = await import("../services/parseProgram.js");
  const parsed = parseRoutesSection(routesText);
  let count = 0;
  const { makeItemKey } = await import("../lib/itemKey.js");
  for (const text of parsed.items) {
    if (votes[makeItemKey("routes", text)] === 1) count += 1;
  }
  return count;
}
