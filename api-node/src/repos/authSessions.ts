import { createHash, randomBytes, randomUUID } from "node:crypto";
import { query } from "../db/pool.js";

export const AUTH_COOKIE_NAME = "auth_session";

export interface AuthSessionRow {
  id: string;
  user_id: number;
  token_hash: string;
  expires_at: string;
  last_seen_at: string;
  created_at: string;
  user_agent: string | null;
}

export function hashAuthSessionToken(raw: string): string {
  return createHash("sha256").update(raw, "utf8").digest("hex");
}

export function newAuthSessionToken(): string {
  return randomBytes(32).toString("base64url");
}

function toIso(value: Date | string): string {
  return value instanceof Date ? value.toISOString() : String(value);
}

function mapRow(row: AuthSessionRow): AuthSessionRow {
  return {
    ...row,
    user_id: Number(row.user_id),
    expires_at: toIso(row.expires_at),
    last_seen_at: toIso(row.last_seen_at),
    created_at: toIso(row.created_at),
  };
}

export async function createAuthSession(params: {
  userId: number;
  tokenHash: string;
  expiresAt: Date;
  userAgent?: string | null;
}): Promise<AuthSessionRow> {
  const id = randomUUID();
  const now = new Date();
  const ua = (params.userAgent ?? "").trim().slice(0, 512) || null;
  const { rows } = await query<AuthSessionRow>(
    `INSERT INTO auth_sessions (id, user_id, token_hash, expires_at, last_seen_at, created_at, user_agent)
     VALUES ($1, $2, $3, $4, $5, $5, $6)
     RETURNING id, user_id, token_hash, expires_at, last_seen_at, created_at, user_agent`,
    [id, params.userId, params.tokenHash, params.expiresAt, now, ua],
  );
  return mapRow(rows[0]!);
}

export async function getAuthSessionByTokenHash(
  tokenHash: string,
): Promise<AuthSessionRow | null> {
  const { rows } = await query<AuthSessionRow>(
    `SELECT id, user_id, token_hash, expires_at, last_seen_at, created_at, user_agent
     FROM auth_sessions WHERE token_hash = $1`,
    [tokenHash],
  );
  const row = rows[0];
  return row ? mapRow(row) : null;
}

export async function touchAuthSession(
  sessionId: string,
  ttlDays: number,
): Promise<void> {
  await query(
    `UPDATE auth_sessions
     SET last_seen_at = NOW(),
         expires_at = NOW() + make_interval(days => $2::int)
     WHERE id = $1
       AND last_seen_at < NOW() - interval '1 hour'`,
    [sessionId, ttlDays],
  );
}

export async function deleteAuthSessionById(sessionId: string): Promise<void> {
  await query(`DELETE FROM auth_sessions WHERE id = $1`, [sessionId]);
}

export async function deleteAuthSessionByTokenHash(
  tokenHash: string,
): Promise<void> {
  await query(`DELETE FROM auth_sessions WHERE token_hash = $1`, [tokenHash]);
}

export async function deleteExpiredAuthSessions(): Promise<number> {
  const { rowCount } = await query(
    `DELETE FROM auth_sessions WHERE expires_at < NOW()`,
  );
  return rowCount ?? 0;
}
