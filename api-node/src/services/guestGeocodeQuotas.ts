import { config } from "../config.js";
import { isRedisEnabled, getRedis } from "../db/redis.js";

export class GuestGeocodeQuotaError extends Error {
  readonly limit: number;
  readonly windowSec: number;

  constructor(message: string, limit: number, windowSec: number) {
    super(message);
    this.limit = limit;
    this.windowSec = windowSec;
  }
}

function bucketKey(sessionId: string): string {
  const window = config.guestGeocodeQuotaWindowSec;
  const slot = Math.floor(Date.now() / 1000 / window);
  return `guest_geocode:${sessionId}:${slot}`;
}

export async function checkAndConsumeGuestGeocodeQuota(
  sessionId: string,
): Promise<void> {
  if (!config.guestGeocodeQuotasEnabled || !isRedisEnabled()) {
    return;
  }
  const limit = config.guestGeocodeQuotaPerHour;
  const window = config.guestGeocodeQuotaWindowSec;
  const key = bucketKey(sessionId);
  const redis = await getRedis();
  const count = await redis.incr(key);
  if (count === 1) {
    await redis.expire(key, window);
  }
  if (count > limit) {
    await redis.decr(key);
    throw new GuestGeocodeQuotaError(
      `Слишком много запросов геокодера (${limit} в час). Попробуйте позже или зарегистрируйтесь.`,
      limit,
      window,
    );
  }
}
