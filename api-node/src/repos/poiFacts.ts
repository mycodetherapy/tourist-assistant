import { query } from "../db/pool.js";

export const POI_FACT_NOT_FOUND = "Справка по месту не найдена в Wikipedia";

export type PoiFactStatus = "pending" | "ready" | "failed";

export interface PoiFactRow {
  cache_key: string;
  poi_name: string;
  city: string;
  status: PoiFactStatus;
  text: string | null;
  source_kind: string | null;
  used_llm: boolean;
  error: string | null;
  updated_at: Date;
}

function mapRow(row: {
  cache_key: string;
  poi_name: string;
  city: string;
  status: string;
  text: string | null;
  source_kind: string | null;
  used_llm: boolean;
  error: string | null;
  updated_at: Date;
}): PoiFactRow {
  return {
    cache_key: row.cache_key,
    poi_name: row.poi_name,
    city: row.city,
    status: row.status as PoiFactStatus,
    text: row.text,
    source_kind: row.source_kind,
    used_llm: Boolean(row.used_llm),
    error: row.error,
    updated_at: row.updated_at,
  };
}

export async function getPoiFact(cacheKey: string): Promise<PoiFactRow | null> {
  const { rows } = await query<PoiFactRow>(
    `SELECT cache_key, poi_name, city, status, text, source_kind, used_llm, error, updated_at
     FROM poi_facts WHERE cache_key = $1`,
    [cacheKey],
  );
  const row = rows[0];
  return row ? mapRow(row) : null;
}

export async function upsertPoiFactPending(params: {
  cacheKey: string;
  poiName: string;
  city: string;
  sourceKind: string;
}): Promise<PoiFactRow> {
  const now = new Date();
  const { rows } = await query<PoiFactRow>(
    `INSERT INTO poi_facts (cache_key, poi_name, city, status, source_kind, used_llm, created_at, updated_at)
     VALUES ($1, $2, $3, 'pending', $4, false, $5, $5)
     ON CONFLICT (cache_key) DO UPDATE SET
       poi_name = EXCLUDED.poi_name,
       city = EXCLUDED.city,
       status = 'pending',
       text = NULL,
       source_kind = EXCLUDED.source_kind,
       used_llm = false,
       error = NULL,
       updated_at = EXCLUDED.updated_at
     RETURNING cache_key, poi_name, city, status, text, source_kind, used_llm, error, updated_at`,
    [params.cacheKey, params.poiName, params.city, params.sourceKind, now],
  );
  return mapRow(rows[0]!);
}

export function isPendingStale(updatedAt: Date): boolean {
  const ageMs = Date.now() - updatedAt.getTime();
  return ageMs > 3 * 60 * 1000;
}

export function toPoiFactResponse(row: PoiFactRow) {
  return {
    cache_key: row.cache_key,
    name: row.poi_name,
    status: row.status,
    text: row.text,
    error: row.error,
  };
}

export function looksLikeSearchGarbage(text: string): boolean {
  const blob = (text || "").trim();
  if (!blob) return true;
  if (blob.length < 280) return true;
  if (
    /столица республики|административный центр городского округа|население города/i.test(
      blob,
    ) &&
    !/собор|кремл|театр|музей|памятник|вознесен/i.test(blob)
  ) {
    return true;
  }
  if ((blob.match(/\.\.\./g) || []).length >= 2) return true;
  const punct = (blob.match(/[.!?]/g) || []).length;
  if (blob.length > 180 && punct < 2) return true;
  if (blob.length > 120 && punct === 0) return true;
  return false;
}
