import { config } from "../config.js";
import { isRedisEnabled, getRedis } from "../db/redis.js";

export class RunQuotaError extends Error {
  readonly limit: number;
  readonly windowSec: number;

  constructor(message: string, limit: number, windowSec: number) {
    super(message);
    this.limit = limit;
    this.windowSec = windowSec;
  }
}

function bucketKey(userId: number, scope: string): string {
  const bucket = scope === "full" ? "full" : "partial";
  const window = config.runQuotaWindowSec;
  const slot = Math.floor(Date.now() / 1000 / window);
  return `run_quota:${userId}:${bucket}:${slot}`;
}

export async function checkAndConsumeRunQuota(
  userId: number,
  scope: string,
): Promise<void> {
  if (!config.runQuotasEnabled || !isRedisEnabled()) {
    return;
  }
  const limit =
    scope === "full"
      ? config.runQuotaFullPerHour
      : config.runQuotaPartialPerHour;
  const window = config.runQuotaWindowSec;
  const key = bucketKey(userId, scope);
  const redis = await getRedis();
  const count = await redis.incr(key);
  if (count === 1) {
    await redis.expire(key, window);
  }
  if (count > limit) {
    await redis.decr(key);
    const label =
      scope === "full" ? "полных сборок" : "пересборок маршрутов";
    throw new RunQuotaError(
      `Лимит ${label}: ${limit} в час. Попробуйте позже.`,
      limit,
      window,
    );
  }
}
