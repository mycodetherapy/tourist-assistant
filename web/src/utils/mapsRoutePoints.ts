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

export type MapsRoutingMode = "pedestrian" | "auto" | "masstransit" | "bicycle";

/** Режим маршрута из rtt в deep link (по умолчанию — пеший, как в route_url.py). */
export function parseMapsRoutingMode(url: string): MapsRoutingMode {
  try {
    const rtt = new URL(url.trim()).searchParams.get("rtt");
    if (rtt === "pd") {
      return "pedestrian";
    }
    if (rtt === "mt") {
      return "masstransit";
    }
    if (rtt === "bc") {
      return "bicycle";
    }
    if (rtt === "auto") {
      return "auto";
    }
    return "pedestrian";
  } catch {
    return "pedestrian";
  }
}
