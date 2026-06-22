import { query } from "../db/pool.js";

export interface GraphRunRow {
  run_id: string;
  trip_id: number;
  user_id: number;
  scope: string;
  status: string;
  error: string | null;
  version_id: number | null;
  graph_run_id: string | null;
  city_fact_status: string;
}

export async function createGraphRun(params: {
  userId: number;
  tripId: number;
  scope: string;
  cityFactStatus: string;
}): Promise<string> {
  const { rows } = await query<{ id: string }>(
    `INSERT INTO graph_runs (id, user_id, trip_id, scope, status, city_fact_status, created_at)
     VALUES (gen_random_uuid(), $1, $2, $3, 'queued', $4, NOW())
     RETURNING id::text`,
    [params.userId, params.tripId, params.scope, params.cityFactStatus],
  );
  return rows[0]!.id;
}

export async function getGraphRun(runId: string): Promise<GraphRunRow | null> {
  const { rows } = await query<{
    id: string;
    trip_id: string;
    user_id: string;
    scope: string;
    status: string;
    error: string | null;
    version_id: string | null;
    graph_run_id: string | null;
    city_fact_status: string;
  }>(
    `SELECT id::text, trip_id, user_id, scope, status, error, version_id, graph_run_id, city_fact_status
     FROM graph_runs WHERE id = $1::uuid`,
    [runId],
  );
  const row = rows[0];
  if (!row) return null;
  return {
    run_id: row.id,
    trip_id: Number(row.trip_id),
    user_id: Number(row.user_id),
    scope: row.scope,
    status: row.status,
    error: row.error,
    version_id: row.version_id ? Number(row.version_id) : null,
    graph_run_id: row.graph_run_id,
    city_fact_status: row.city_fact_status,
  };
}

export async function hasActiveGraphRun(tripId: number): Promise<boolean> {
  const { rows } = await query<{ id: string }>(
    `SELECT id::text FROM graph_runs
     WHERE trip_id = $1 AND status IN ('queued', 'running')
     LIMIT 1`,
    [tripId],
  );
  return rows.length > 0;
}

export async function failStaleGraphRuns(
  tripId: number,
  maxAgeSec: number,
): Promise<number> {
  const { rowCount } = await query(
    `UPDATE graph_runs SET
       status = 'failed',
       error = 'Прогон прерван (timeout). Запустите сборку снова.',
       finished_at = NOW()
     WHERE trip_id = $1
       AND status IN ('queued', 'running')
       AND (
         (status = 'queued' AND created_at < NOW() - make_interval(secs => $2))
         OR (status = 'running' AND COALESCE(started_at, created_at) < NOW() - make_interval(secs => $2))
       )`,
    [tripId, maxAgeSec],
  );
  if ((rowCount ?? 0) > 0) {
    await releaseTripBuildLock(tripId);
  }
  return rowCount ?? 0;
}

export async function updateGraphRun(
  runId: string,
  fields: Record<string, unknown>,
): Promise<void> {
  const sets: string[] = [];
  const values: unknown[] = [];
  let i = 1;
  for (const [key, value] of Object.entries(fields)) {
    sets.push(`${key} = $${i++}`);
    values.push(value);
  }
  if (!sets.length) return;
  values.push(runId);
  await query(
    `UPDATE graph_runs SET ${sets.join(", ")} WHERE id = $${i}::uuid`,
    values,
  );
}

export async function acquireTripBuildLock(
  tripId: number,
  ttlSec = 3600,
): Promise<boolean> {
  const { getRedis } = await import("../db/redis.js");
  const redis = await getRedis();
  const result = await redis.set(`trip:${tripId}:build_lock`, "1", {
    NX: true,
    EX: ttlSec,
  });
  return result === "OK";
}

export async function releaseTripBuildLock(tripId: number): Promise<void> {
  const { getRedis } = await import("../db/redis.js");
  const redis = await getRedis();
  await redis.del(`trip:${tripId}:build_lock`);
}
