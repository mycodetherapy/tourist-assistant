import { config } from "../config.js";
import { isRedisEnabled, getRedis } from "../db/redis.js";

export class FreeRunQuotaError extends Error {
  readonly limit: number;
  readonly windowSec: number;

  constructor(message: string, limit: number, windowSec: number) {
    super(message);
    this.limit = limit;
    this.windowSec = windowSec;
  }
}

function bucketKey(userId: number): string {
  const window = config.freeRunQuotaWindowSec;
  const slot = Math.floor(Date.now() / 1000 / window);
  return `free_run_quota:${userId}:${slot}`;
}

export async function checkAndConsumeFreeRunQuota(
  userId: number,
): Promise<void> {
  if (!config.freeRunQuotasEnabled || !isRedisEnabled()) {
    return;
  }
  const limit = config.freeRunQuotaPerDay;
  const window = config.freeRunQuotaWindowSec;
  const key = bucketKey(userId);
  const redis = await getRedis();
  const count = await redis.incr(key);
  if (count === 1) {
    await redis.expire(key, window);
  }
  if (count > limit) {
    await redis.decr(key);
    throw new FreeRunQuotaError(
      `Лимит бесплатных сборок: ${limit} в сутки. Попробуйте завтра или включите AI в настройках.`,
      limit,
      window,
    );
  }
}
