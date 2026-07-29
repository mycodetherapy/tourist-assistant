import { createHash } from "node:crypto";

export function makeItemKey(section: string, text: string): string {
  const normalized = text.trim().toLowerCase().replace(/\s+/g, " ");
  const payload = `${section}:${normalized}`;
  return createHash("sha256").update(payload, "utf8").digest("hex").slice(0, 16);
}

export function makeRouteStopKey(poiId: string): string {
  const pid = poiId.trim();
  if (!pid) throw new Error("poi_id required");
  return `poi:${pid}`;
}

export function parseRouteStopKey(itemKey: string): string | null {
  const key = itemKey.trim();
  if (key.startsWith("poi:") && key.length > 4) {
    return key.slice(4);
  }
  return null;
}
