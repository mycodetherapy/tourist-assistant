/** Парсинг rtext из deep link Яндекс.Карт (как search/yandex/route_url.py). */

export interface MapRoutePoint {
  lat: number;
  lon: number;
}

export function parseMapsRoutePoints(url: string): MapRoutePoint[] {
  const trimmed = url.trim();
  if (!trimmed) {
    return [];
  }
  try {
    const parsed = new URL(trimmed);
    const rtext = parsed.searchParams.get("rtext") ?? "";
    const points: MapRoutePoint[] = [];
    for (const part of rtext.split("~")) {
      const chunk = part.trim();
      if (!chunk.includes(",")) {
        continue;
      }
      const [latRaw, lonRaw] = chunk.split(",", 2);
      const lat = Number.parseFloat(latRaw);
      const lon = Number.parseFloat(lonRaw);
      if (Number.isFinite(lat) && Number.isFinite(lon)) {
        points.push({ lat, lon });
      }
    }
    return points;
  } catch {
    return [];
  }
}
