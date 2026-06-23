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

function haversineMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const earthRadius = 6_371_000;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * earthRadius * Math.asin(Math.sqrt(a));
}

function pointsAreClose(a: MapRoutePoint, b: MapRoutePoint, meters = 80): boolean {
  return haversineMeters(a.lat, a.lon, b.lat, b.lon) < meters;
}

export interface RouteMapMarkers {
  /** Базовая точка (отель) — без номера на карте. */
  anchor: MapRoutePoint | null;
  /** Остановки маршрута — нумеруются с 1. */
  leisureStops: MapRoutePoint[];
}

function geoToMapPoint(point: { lat: number; lon: number }): MapRoutePoint {
  return { lat: point.lat, lon: point.lon };
}

export interface StoredRouteMapMarkers {
  anchor?: { lat: number; lon: number } | null;
  leisureCoords?: { lat: number; lon: number }[];
}

/**
 * Точки для меток на карте: базовая точка отдельно, нумерация только у leisure stops.
 * При наличии route_map_* с бэкенда — без эвристик по rtext.
 */
export function resolveRouteMapMarkers(
  routePoints: MapRoutePoint[],
  leisureStopCount: number,
  stored?: StoredRouteMapMarkers,
): RouteMapMarkers {
  const storedLeisure = stored?.leisureCoords ?? [];
  if (storedLeisure.length > 0) {
    return {
      anchor: stored?.anchor ? geoToMapPoint(stored.anchor) : null,
      leisureStops: storedLeisure.map(geoToMapPoint),
    };
  }

  if (leisureStopCount <= 0 || routePoints.length === 0) {
    return { anchor: null, leisureStops: [] };
  }

  if (routePoints.length === leisureStopCount) {
    if (stored?.anchor) {
      return {
        anchor: geoToMapPoint(stored.anchor),
        leisureStops: routePoints,
      };
    }
    return { anchor: null, leisureStops: routePoints };
  }

  const first = routePoints[0];
  const last = routePoints[routePoints.length - 1];
  const loopClosed = pointsAreClose(first, last);

  if (routePoints.length === leisureStopCount + 1) {
    if (loopClosed) {
      return { anchor: null, leisureStops: routePoints.slice(0, leisureStopCount) };
    }
    return { anchor: first, leisureStops: routePoints.slice(1) };
  }

  if (routePoints.length === leisureStopCount + 2 && loopClosed) {
    return { anchor: first, leisureStops: routePoints.slice(1, -1) };
  }

  if (routePoints.length > leisureStopCount) {
    return { anchor: first, leisureStops: routePoints.slice(1, 1 + leisureStopCount) };
  }

  return { anchor: null, leisureStops: routePoints.slice(0, leisureStopCount) };
}

/** Точки из maps_route_url для внешней ссылки (без дубля замыкания кольца). */
export function routePointsForYandexOpen(mapsRouteUrl: string): MapRoutePoint[] {
  const points = parseMapsRoutePoints(mapsRouteUrl);
  if (points.length >= 2 && pointsAreClose(points[0], points[points.length - 1])) {
    return points.slice(0, -1);
  }
  return points;
}
