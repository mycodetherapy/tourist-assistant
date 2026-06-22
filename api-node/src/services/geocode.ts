import { config } from "../config.js";
import { isAcceptableGeoMember } from "../lib/poiFilters.js";

const NOMINATIM_URL =
  process.env.NOMINATIM_URL?.replace(/\/$/, "") ||
  "https://nominatim.openstreetmap.org";
const USER_AGENT =
  process.env.NOMINATIM_USER_AGENT ||
  "tourist-assistant/1.0 (node api; contact: dev@localhost)";
const YANDEX_MIN_INTERVAL_MS = 350;

let lastYandexCall = 0;

export interface GeocodeResult {
  lat: number;
  lon: number;
  label: string;
}

async function throttleYandex(): Promise<void> {
  const elapsed = Date.now() - lastYandexCall;
  if (elapsed < YANDEX_MIN_INTERVAL_MS) {
    await new Promise((r) => setTimeout(r, YANDEX_MIN_INTERVAL_MS - elapsed));
  }
  lastYandexCall = Date.now();
}

async function yandexGeocode(
  query: string,
  cityHint: string,
  results: number,
): Promise<GeocodeResult[]> {
  const key = config.yandexMapsApiKey;
  if (!key) return [];
  await throttleYandex();
  const params = new URLSearchParams({
    apikey: key,
    geocode: query,
    format: "json",
    results: String(results),
  });
  const res = await fetch(
    `https://geocode-maps.yandex.ru/1.x/?${params}`,
    { signal: AbortSignal.timeout(15000) },
  );
  if (!res.ok) return [];
  const data = (await res.json()) as {
    response?: {
      GeoObjectCollection?: {
        featureMember?: Array<{
          GeoObject?: {
            Point?: { pos?: string };
            name?: string;
            metaDataProperty?: {
              GeocoderMetaData?: {
                kind?: string;
                text?: string;
                Address?: { formatted?: string };
              };
            };
          };
        }>;
      };
    };
  };
  const members = data.response?.GeoObjectCollection?.featureMember ?? [];
  const out: GeocodeResult[] = [];
  for (const member of members) {
    if (!isAcceptableGeoMember(member, cityHint)) continue;
    const obj = member.GeoObject;
    const pos = obj?.Point?.pos;
    if (!pos) continue;
    const [lonStr, latStr] = pos.split(" ");
    const lat = Number(latStr);
    const lon = Number(lonStr);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
    const meta = obj.metaDataProperty?.GeocoderMetaData;
    const label = String(
      meta?.Address?.formatted ||
        meta?.text ||
        obj.name ||
        query,
    ).trim();
    out.push({ lat, lon, label });
  }
  return out;
}

export async function geocodePlaces(
  query: string,
  cityHint: string,
): Promise<GeocodeResult[]> {
  const trimmedQuery = query.trim();
  const hint = cityHint.trim();
  let results = await yandexGeocode(trimmedQuery, hint, 5);

  if (!results.length && hint) {
    const nominatimQuery =
      hint && hint !== trimmedQuery
        ? `${trimmedQuery}, ${hint}`
        : trimmedQuery || hint;
    if (nominatimQuery) {
      const center = await resolveCityCenter(nominatimQuery);
      if (center) results = [center];
    }
  }

  return results;
}

export async function reverseGeocodeLabel(
  lat: number,
  lon: number,
  cityHint: string,
): Promise<string | null> {
  const key = config.yandexMapsApiKey;
  if (key) {
    await throttleYandex();
    const yandexResults = await yandexGeocode(`${lon},${lat}`, cityHint, 1);
    if (yandexResults[0]?.label) return yandexResults[0].label;
  }
  return nominatimReverse(lat, lon);
}

async function nominatimReverse(lat: number, lon: number): Promise<string | null> {
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    format: "json",
  });
  const res = await fetch(`${NOMINATIM_URL}/reverse?${params}`, {
    headers: { "User-Agent": USER_AGENT },
    signal: AbortSignal.timeout(15000),
  });
  if (!res.ok) return null;
  const data = (await res.json()) as { display_name?: string };
  return data.display_name?.trim() ?? null;
}

export async function resolveCityCenter(
  city: string,
): Promise<GeocodeResult | null> {
  const params = new URLSearchParams({
    q: city,
    format: "json",
    limit: "1",
  });
  const res = await fetch(`${NOMINATIM_URL}/search?${params}`, {
    headers: { "User-Agent": USER_AGENT },
    signal: AbortSignal.timeout(15000),
  });
  if (!res.ok) return null;
  const data = (await res.json()) as Array<{
    lat?: string;
    lon?: string;
    display_name?: string;
  }>;
  const row = data[0];
  if (!row?.lat || !row.lon) return null;
  return {
    lat: Number(row.lat),
    lon: Number(row.lon),
    label: row.display_name?.trim() || city,
  };
}
