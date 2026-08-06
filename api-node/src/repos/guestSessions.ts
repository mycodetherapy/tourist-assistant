import { randomUUID } from "node:crypto";
import { query } from "../db/pool.js";

export const GUEST_COOKIE_NAME = "guest_session";

export interface GuestSessionRow {
  id: string;
  user_id: number;
  trip_id: number | null;
  full_runs_used: number;
  partial_runs_used: number;
  expires_at: string;
  created_at: string;
}

function toIso(value: Date | string): string {
  return value instanceof Date ? value.toISOString() : String(value);
}

export async function getGuestSessionById(
  sessionId: string,
): Promise<GuestSessionRow | null> {
  const { rows } = await query<GuestSessionRow>(
    `SELECT id, user_id, trip_id, full_runs_used, partial_runs_used, expires_at, created_at
     FROM guest_sessions WHERE id = $1`,
    [sessionId],
  );
  const row = rows[0];
  if (!row) return null;
  return {
    ...row,
    user_id: Number(row.user_id),
    trip_id: row.trip_id != null ? Number(row.trip_id) : null,
    full_runs_used: Number(row.full_runs_used),
    partial_runs_used: Number(row.partial_runs_used),
    expires_at: toIso(row.expires_at),
    created_at: toIso(row.created_at),
  };
}

export async function createGuestSession(params: {
  userId: number;
  expiresAt: Date;
}): Promise<GuestSessionRow> {
  const id = randomUUID();
  const now = new Date();
  const { rows } = await query<GuestSessionRow>(
    `INSERT INTO guest_sessions (id, user_id, trip_id, full_runs_used, partial_runs_used, expires_at, created_at)
     VALUES ($1, $2, NULL, 0, 0, $3, $4)
     RETURNING id, user_id, trip_id, full_runs_used, partial_runs_used, expires_at, created_at`,
    [id, params.userId, params.expiresAt, now],
  );
  const row = rows[0]!;
  return {
    ...row,
    user_id: Number(row.user_id),
    trip_id: row.trip_id != null ? Number(row.trip_id) : null,
    full_runs_used: Number(row.full_runs_used),
    partial_runs_used: Number(row.partial_runs_used),
    expires_at: toIso(row.expires_at),
    created_at: toIso(row.created_at),
  };
}

export async function setGuestSessionTrip(
  sessionId: string,
  tripId: number,
): Promise<void> {
  await query(
    `UPDATE guest_sessions SET trip_id = $2 WHERE id = $1`,
    [sessionId, tripId],
  );
}

export async function incrementGuestFullRuns(sessionId: string): Promise<void> {
  await query(
    `UPDATE guest_sessions SET full_runs_used = full_runs_used + 1 WHERE id = $1`,
    [sessionId],
  );
}

export async function incrementGuestPartialRuns(sessionId: string): Promise<void> {
  await query(
    `UPDATE guest_sessions SET partial_runs_used = partial_runs_used + 1 WHERE id = $1`,
    [sessionId],
  );
}

export async function deleteGuestSession(sessionId: string): Promise<void> {
  await query(`DELETE FROM guest_sessions WHERE id = $1`, [sessionId]);
}

export async function transferGuestUserData(
  guestUserId: number,
  targetUserId: number,
): Promise<number | null> {
  const { rows } = await query<{ trip_id: string | null }>(
    `SELECT trip_id FROM guest_sessions WHERE user_id = $1 LIMIT 1`,
    [guestUserId],
  );
  const tripId = rows[0]?.trip_id != null ? Number(rows[0].trip_id) : null;

  await query(`UPDATE trips SET user_id = $2 WHERE user_id = $1`, [
    guestUserId,
    targetUserId,
  ]);
  await query(`UPDATE graph_runs SET user_id = $2 WHERE user_id = $1`, [
    guestUserId,
    targetUserId,
  ]);
  await query(`DELETE FROM guest_sessions WHERE user_id = $1`, [guestUserId]);
  await query(`DELETE FROM users WHERE id = $1 AND is_guest = true`, [guestUserId]);

  return tripId;
}
