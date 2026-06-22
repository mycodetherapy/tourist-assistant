import { config } from "../config.js";

const NOMINATIM_URL =
  process.env.NOMINATIM_URL?.replace(/\/$/, "") ||
  "https://nominatim.openstreetmap.org";
const USER_AGENT =
  process.env.NOMINATIM_USER_AGENT ||
  "tourist-assistant/1.0 (node api; contact: dev@localhost)";

export interface GeocodeResult {
  lat: number;
  lon: number;
  label: string;
}

export async function geocodePlaces(
  query: string,
  cityHint: string,
): Promise<GeocodeResult[]> {
  const key = config.yandexMapsApiKey;
  const results: GeocodeResult[] = [];

  if (key) {
    const params = new URLSearchParams({
      apikey: key,
      geocode: query,
      format: "json",
      results: "5",
    });
    const res = await fetch(
      `https://geocode-maps.yandex.ru/1.x/?${params}`,
      { signal: AbortSignal.timeout(15000) },
    );
    if (res.ok) {
      const data = (await res.json()) as {
        response?: {
          GeoObjectCollection?: {
            featureMember?: Array<{
              GeoObject?: {
                Point?: { pos?: string };
                metaDataProperty?: {
                  GeocoderMetaData?: {
                    Address?: { formatted?: string };
                    text?: string;
                  };
                };
                name?: string;
              };
            }>;
          };
        };
      };
      const members =
        data.response?.GeoObjectCollection?.featureMember ?? [];
      for (const member of members) {
        const obj = member.GeoObject;
        const pos = obj?.Point?.pos;
        if (!pos) continue;
        const [lonStr, latStr] = pos.split(" ");
        const lat = Number(latStr);
        const lon = Number(lonStr);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
        const meta = obj.metaDataProperty?.GeocoderMetaData;
        const label =
          meta?.Address?.formatted ||
          meta?.text ||
          obj.name ||
          query;
        results.push({ lat, lon, label: String(label).trim() });
      }
    }
  }

  // Как в Python API: Nominatim, если Яндекс недоступен или ничего не нашёл
  if (!results.length) {
    const nominatimQuery =
      cityHint && cityHint !== query ? `${query}, ${cityHint}` : query || cityHint;
    if (nominatimQuery) {
      const center = await resolveCityCenter(nominatimQuery);
      if (center) results.push(center);
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
    const params = new URLSearchParams({
      apikey: key,
      geocode: `${lon},${lat}`,
      format: "json",
      results: "1",
    });
    const res = await fetch(
      `https://geocode-maps.yandex.ru/1.x/?${params}`,
      { signal: AbortSignal.timeout(15000) },
    );
    if (res.ok) {
      const data = (await res.json()) as {
        response?: {
          GeoObjectCollection?: {
            featureMember?: Array<{
              GeoObject?: {
                metaDataProperty?: {
                  GeocoderMetaData?: { text?: string };
                };
              };
            }>;
          };
        };
      };
      const text =
        data.response?.GeoObjectCollection?.featureMember?.[0]?.GeoObject
          ?.metaDataProperty?.GeocoderMetaData?.text;
      if (text) return String(text).trim();
    }
  }
  const nom = await nominatimReverse(lat, lon);
  return nom;
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
