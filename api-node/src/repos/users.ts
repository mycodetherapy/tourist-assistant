import { query } from "../db/pool.js";

export interface User {
  id: number;
  email: string;
  password_hash: string | null;
  google_sub: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserSettingsRow {
  user_id: number;
  llm_api_key_enc: string | null;
  llm_base_url: string | null;
  llm_model: string | null;
  llm_mode: string;
  updated_at: string;
}

function toIso(value: Date | string): string {
  return value instanceof Date ? value.toISOString() : String(value);
}

export async function createUser(params: {
  email: string;
  password_hash?: string | null;
  google_sub?: string | null;
  is_guest?: boolean;
}): Promise<User> {
  const email = params.email.trim().toLowerCase();
  const now = new Date();
  const { rows } = await query<User>(
    `INSERT INTO users (email, password_hash, google_sub, is_guest, created_at, updated_at)
     VALUES ($1, $2, $3, $4, $5, $5)
     RETURNING id, email, password_hash, google_sub, created_at, updated_at`,
    [
      email,
      params.password_hash ?? null,
      params.google_sub ?? null,
      params.is_guest ?? false,
      now,
    ],
  );
  const row = rows[0]!;
  return {
    ...row,
    created_at: toIso(row.created_at),
    updated_at: toIso(row.updated_at),
  };
}

export async function getUserById(userId: number): Promise<User | null> {
  const { rows } = await query<User>(
    `SELECT id, email, password_hash, google_sub, created_at, updated_at
     FROM users WHERE id = $1`,
    [userId],
  );
  const row = rows[0];
  if (!row) return null;
  return {
    ...row,
    created_at: toIso(row.created_at),
    updated_at: toIso(row.updated_at),
  };
}

export async function getUserByGoogleSub(googleSub: string): Promise<User | null> {
  const { rows } = await query<User>(
    `SELECT id, email, password_hash, google_sub, created_at, updated_at
     FROM users WHERE google_sub = $1`,
    [googleSub],
  );
  const row = rows[0];
  if (!row) return null;
  return {
    ...row,
    created_at: toIso(row.created_at),
    updated_at: toIso(row.updated_at),
  };
}

export async function linkGoogleSub(userId: number, googleSub: string): Promise<void> {
  const now = new Date();
  await query(
    `UPDATE users SET google_sub = $1, updated_at = $2 WHERE id = $3`,
    [googleSub, now, userId],
  );
}

export async function getUserByEmail(email: string): Promise<User | null> {
  const normalized = email.trim().toLowerCase();
  const { rows } = await query<User>(
    `SELECT id, email, password_hash, google_sub, created_at, updated_at
     FROM users WHERE lower(email) = $1`,
    [normalized],
  );
  const row = rows[0];
  if (!row) return null;
  return {
    ...row,
    created_at: toIso(row.created_at),
    updated_at: toIso(row.updated_at),
  };
}

export async function getUserSettings(
  userId: number,
): Promise<UserSettingsRow | null> {
  const { rows } = await query<UserSettingsRow>(
    `SELECT user_id, llm_api_key_enc, llm_base_url, llm_model, llm_mode, updated_at
     FROM user_settings WHERE user_id = $1`,
    [userId],
  );
  const row = rows[0];
  if (!row) return null;
  return {
    ...row,
    llm_mode: row.llm_mode || "none",
    updated_at: toIso(row.updated_at),
  };
}

export async function upsertUserSettings(
  userId: number,
  fields: {
    llm_api_key_enc?: string | null;
    llm_base_url?: string | null;
    llm_model?: string | null;
    llm_mode?: string | null;
    clear_llm_key?: boolean;
  },
): Promise<UserSettingsRow> {
  const existing = await getUserSettings(userId);
  const enc = fields.clear_llm_key
    ? null
    : fields.llm_api_key_enc !== undefined
      ? fields.llm_api_key_enc
      : (existing?.llm_api_key_enc ?? null);
  const baseUrl =
    fields.llm_base_url !== undefined
      ? fields.llm_base_url
      : (existing?.llm_base_url ?? null);
  const model =
    fields.llm_model !== undefined ? fields.llm_model : (existing?.llm_model ?? null);
  let llmMode =
    fields.llm_mode !== undefined && fields.llm_mode !== null
      ? fields.llm_mode
      : (existing?.llm_mode ?? "none");
  if (fields.clear_llm_key && llmMode === "byok") {
    llmMode = "none";
  }
  const now = new Date();
  await query(
    `INSERT INTO user_settings (user_id, llm_api_key_enc, llm_base_url, llm_model, llm_mode, updated_at)
     VALUES ($1, $2, $3, $4, $5, $6)
     ON CONFLICT (user_id) DO UPDATE SET
       llm_api_key_enc = EXCLUDED.llm_api_key_enc,
       llm_base_url = EXCLUDED.llm_base_url,
       llm_model = EXCLUDED.llm_model,
       llm_mode = EXCLUDED.llm_mode,
       updated_at = EXCLUDED.updated_at`,
    [userId, enc, baseUrl, model, llmMode, now],
  );
  const row = await getUserSettings(userId);
  if (!row) throw new Error("settings upsert failed");
  return row;
}

export async function clearUserLlmKey(userId: number): Promise<void> {
  await upsertUserSettings(userId, { clear_llm_key: true });
}

export async function getUserProfile(
  userId: number,
): Promise<Record<string, unknown> | null> {
  const { rows } = await query<{ preferences_json: Record<string, unknown> }>(
    `SELECT preferences_json FROM user_profile WHERE user_id = $1`,
    [userId],
  );
  if (rows[0]) return rows[0].preferences_json;
  const latest = await query<{ preferences_json: Record<string, unknown> }>(
    `SELECT tp.preferences_json
     FROM trip_preferences tp
     JOIN trips t ON t.id = tp.trip_id
     WHERE t.user_id = $1
     ORDER BY t.updated_at DESC
     LIMIT 1`,
    [userId],
  );
  return latest.rows[0]?.preferences_json ?? null;
}

export async function saveUserProfile(
  userId: number,
  preferences: Record<string, unknown>,
): Promise<void> {
  const now = new Date();
  await query(
    `INSERT INTO user_profile (user_id, preferences_json, updated_at)
     VALUES ($1, $2::jsonb, $3)
     ON CONFLICT (user_id) DO UPDATE SET
       preferences_json = EXCLUDED.preferences_json,
       updated_at = EXCLUDED.updated_at`,
    [userId, JSON.stringify(preferences), now],
  );
}

/** Обновляет last_seen_at не чаще раза в минуту (debounce на уровне SQL). */
export async function touchUserLastSeen(userId: number): Promise<void> {
  await query(
    `UPDATE users
     SET last_seen_at = NOW()
     WHERE id = $1
       AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '1 minute')`,
    [userId],
  );
}

export async function createGuestUser(): Promise<User> {
  const { randomUUID } = await import("node:crypto");
  const suffix = randomUUID().replace(/-/g, "").slice(0, 16);
  const email = `guest+${suffix}@guest.progulyai.local`;
  const user = await createUser({ email, is_guest: true });
  await upsertUserSettings(user.id, { llm_mode: "none" });
  return user;
}

export async function isGuestUser(userId: number): Promise<boolean> {
  const { rows } = await query<{ is_guest: boolean }>(
    `SELECT is_guest FROM users WHERE id = $1`,
    [userId],
  );
  return Boolean(rows[0]?.is_guest);
}
