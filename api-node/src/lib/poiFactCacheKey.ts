import { createHash } from "node:crypto";

const WIKIDATA_QID_RE = /^Q\d+$/i;
const OSM_POI_RE = /^osm_(node|way|relation)_\d+$/i;

export function extractWikidataQid(poiId: string): string | null {
  const raw = (poiId || "").trim();
  if (!raw) return null;
  if (WIKIDATA_QID_RE.test(raw)) return raw.toUpperCase();
  if (raw.toLowerCase().startsWith("wikidata_")) {
    const qid = raw.replace(/^wikidata_/i, "").trim();
    if (WIKIDATA_QID_RE.test(qid)) return qid.toUpperCase();
  }
  return null;
}

export function normalizePoiFactCacheKey(params: {
  poiId?: string | null;
  name: string;
  city: string;
}): string {
  const pid = (params.poiId || "").trim();
  const qid = extractWikidataQid(pid);
  if (qid) return qid;
  if (OSM_POI_RE.test(pid)) return pid;
  const blob = `${params.city.trim().toLowerCase()}|${params.name.trim().toLowerCase()}`;
  const digest = createHash("sha256").update(blob, "utf8").digest("hex").slice(0, 24);
  return `search_${digest}`;
}
