import { randomUUID } from "node:crypto";
import { query } from "../db/pool.js";

export type OsrmPrepareStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export type OsrmPrepareJob = {
  id: string;
  user_id: number;
  slug: string;
  status: OsrmPrepareStatus;
  stage: string;
  progress: number;
  error: string | null;
  counts_against_quota: boolean;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
};

function toIso(value: Date | string | null | undefined): string | null {
  if (value == null) return null;
  return value instanceof Date ? value.toISOString() : String(value);
}

function mapJob(row: OsrmPrepareJob): OsrmPrepareJob {
  return {
    ...row,
    user_id: Number(row.user_id),
    progress: Number(row.progress),
    counts_against_quota: Boolean(row.counts_against_quota),
    created_at: toIso(row.created_at)!,
    updated_at: toIso(row.updated_at)!,
    finished_at: toIso(row.finished_at),
  };
}

export async function createOsrmPrepareJob(params: {
  userId: number;
  slug: string;
  countsAgainstQuota: boolean;
}): Promise<OsrmPrepareJob> {
  const id = randomUUID();
  const { rows } = await query<OsrmPrepareJob>(
    `INSERT INTO osrm_prepare_jobs (
       id, user_id, slug, status, stage, progress, counts_against_quota
     ) VALUES ($1::uuid, $2, $3, 'queued', 'queued', 0, $4)
     RETURNING id, user_id, slug, status, stage, progress, error,
               counts_against_quota, created_at, updated_at, finished_at`,
    [id, params.userId, params.slug, params.countsAgainstQuota],
  );
  return mapJob(rows[0]!);
}

export async function getOsrmPrepareJob(id: string): Promise<OsrmPrepareJob | null> {
  const { rows } = await query<OsrmPrepareJob>(
    `SELECT id, user_id, slug, status, stage, progress, error,
            counts_against_quota, created_at, updated_at, finished_at
     FROM osrm_prepare_jobs WHERE id = $1::uuid`,
    [id],
  );
  return rows[0] ? mapJob(rows[0]) : null;
}

export async function findActiveOsrmPrepareJob(
  slug: string,
): Promise<OsrmPrepareJob | null> {
  const { rows } = await query<OsrmPrepareJob>(
    `SELECT id, user_id, slug, status, stage, progress, error,
            counts_against_quota, created_at, updated_at, finished_at
     FROM osrm_prepare_jobs
     WHERE slug = $1 AND status IN ('queued', 'running')
     ORDER BY created_at ASC
     LIMIT 1`,
    [slug],
  );
  return rows[0] ? mapJob(rows[0]) : null;
}

export async function findLatestOsrmPrepareJob(
  slug: string,
): Promise<OsrmPrepareJob | null> {
  const { rows } = await query<OsrmPrepareJob>(
    `SELECT id, user_id, slug, status, stage, progress, error,
            counts_against_quota, created_at, updated_at, finished_at
     FROM osrm_prepare_jobs
     WHERE slug = $1
     ORDER BY created_at DESC
     LIMIT 1`,
    [slug],
  );
  return rows[0] ? mapJob(rows[0]) : null;
}

export async function listUserOsrmPrepareJobs(
  userId: number,
  limit = 20,
): Promise<OsrmPrepareJob[]> {
  const { rows } = await query<OsrmPrepareJob>(
    `SELECT id, user_id, slug, status, stage, progress, error,
            counts_against_quota, created_at, updated_at, finished_at
     FROM osrm_prepare_jobs
     WHERE user_id = $1
     ORDER BY created_at DESC
     LIMIT $2`,
    [userId, limit],
  );
  return rows.map(mapJob);
}
