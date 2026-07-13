import { enqueueCityFact } from "../jobs/enqueue.js";
import { getLatestPendingCityFactRun } from "../repos/graphRuns.js";
import { patchItineraryProgram } from "../repos/trips.js";

const ENQUEUE_LOCK_SEC = 90;
const RETRY_AFTER_MS = 30_000;
const FAIL_AFTER_MS = 10 * 60_000;

export async function recoverCityFactIfNeeded(params: {
  tripId: number;
  userId: number;
  city: string;
  versionId: number;
  program: Record<string, unknown>;
}): Promise<Record<string, unknown>> {
  const status = params.program.city_fact_status;
  const lifehacks = String(params.program.lifehacks ?? "").trim();
  if (status !== "pending" || lifehacks) {
    return params.program;
  }

  const run = await getLatestPendingCityFactRun(params.tripId);
  if (!run?.finished_at) {
    return params.program;
  }

  const ageMs = Date.now() - run.finished_at.getTime();
  if (ageMs >= FAIL_AFTER_MS) {
    await patchItineraryProgram(params.versionId, { city_fact_status: "failed" });
    return { ...params.program, city_fact_status: "failed" };
  }

  if (ageMs < RETRY_AFTER_MS) {
    return params.program;
  }

  const { getRedis } = await import("../db/redis.js");
  const redis = await getRedis();
  const lockKey = `trip:${params.tripId}:city_fact_enqueue`;
  const locked = await redis.set(lockKey, "1", { NX: true, EX: ENQUEUE_LOCK_SEC });
  if (!locked) {
    return params.program;
  }

  await enqueueCityFact(run.run_id, {
    trip_id: params.tripId,
    user_id: params.userId,
    version_id: params.versionId,
    city: params.city,
  });
  return params.program;
}
