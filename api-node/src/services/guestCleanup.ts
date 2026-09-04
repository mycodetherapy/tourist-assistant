import { config } from "../config.js";
import { query } from "../db/pool.js";
import { deleteExpiredAuthSessions } from "../repos/authSessions.js";

export interface GuestCleanupStats {
  deletedUsers: number;
  deletedUserIds: number[];
  deletedAuthSessions: number;
}

/** Удаляет guest-пользователей с истёкшей сессией и «осиротевших» без session row. */
export async function runGuestCleanup(): Promise<GuestCleanupStats> {
  const orphanGraceHours = Math.max(1, config.guestCleanupOrphanGraceHours);
  const { rows } = await query<{ id: string }>(
    `SELECT u.id
     FROM users u
     WHERE u.is_guest = true
       AND (
         EXISTS (
           SELECT 1 FROM guest_sessions gs
           WHERE gs.user_id = u.id AND gs.expires_at < NOW()
         )
         OR (
           NOT EXISTS (SELECT 1 FROM guest_sessions gs WHERE gs.user_id = u.id)
           AND u.created_at < NOW() - make_interval(hours => $1::int)
         )
       )`,
    [orphanGraceHours],
  );
  const ids = rows.map((row) => Number(row.id));
  let deletedAuthSessions = 0;
  try {
    deletedAuthSessions = await deleteExpiredAuthSessions();
  } catch (err) {
    console.error("Auth session cleanup failed", err);
  }
  if (ids.length === 0) {
    return { deletedUsers: 0, deletedUserIds: [], deletedAuthSessions };
  }
  await query(`DELETE FROM users WHERE id = ANY($1::bigint[]) AND is_guest = true`, [
    ids,
  ]);
  return { deletedUsers: ids.length, deletedUserIds: ids, deletedAuthSessions };
}

let cleanupTimer: ReturnType<typeof setInterval> | null = null;

export function startGuestCleanupScheduler(log: (msg: string) => void = console.log): void {
  const intervalSec = config.guestCleanupIntervalSec;
  if (intervalSec <= 0 || cleanupTimer) {
    return;
  }
  const tick = () => {
    void runGuestCleanup()
      .then((stats) => {
        if (stats.deletedUsers > 0 || stats.deletedAuthSessions > 0) {
          log(
            `Guest cleanup: removed ${stats.deletedUsers} expired guest user(s), ${stats.deletedAuthSessions} auth session(s)`,
          );
        }
      })
      .catch((err) => {
        console.error("Guest cleanup failed", err);
      });
  };
  tick();
  cleanupTimer = setInterval(tick, intervalSec * 1000);
}

export function stopGuestCleanupScheduler(): void {
  if (cleanupTimer) {
    clearInterval(cleanupTimer);
    cleanupTimer = null;
  }
}
