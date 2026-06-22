import { createClient, type RedisClientType } from "redis";
import { config } from "../config.js";

let client: RedisClientType | null = null;

export function isRedisEnabled(): boolean {
  return Boolean(config.redisUrl);
}

export async function getRedis(): Promise<RedisClientType> {
  if (!client) {
    if (!config.redisUrl) {
      throw new Error("REDIS_URL is required");
    }
    client = createClient({ url: config.redisUrl });
    client.on("error", (err) => console.error("Redis error", err));
    await client.connect();
  }
  return client;
}

export async function closeRedis(): Promise<void> {
  if (client) {
    await client.quit();
    client = null;
  }
}
