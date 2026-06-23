import type { RouteGeometry, TripRouteCase } from "../api/routeTypes";
import type { MapRoutePoint } from "./mapsRoutePoints";
import { isYandexMapsConfigured } from "./yandexMapsLoader";

export function hasInteractiveRouteGeometry(routeCase: TripRouteCase): boolean {
  if (!isYandexMapsConfigured()) {
    return false;
  }
  const coords = routeCase.route_geometry?.coordinates;
  return Array.isArray(coords) && coords.length >= 2;
}

function shouldSwapGeoJsonCoords(coords: [number, number][]): boolean {
  const sample = coords
    .filter(([a, b]) => Math.abs(a) > 1 && Math.abs(b) > 1)
    .slice(0, 80);
  if (sample.length === 0) {
    return false;
  }
  const avg0 = sample.reduce((sum, [a]) => sum + a, 0) / sample.length;
  const avg1 = sample.reduce((sum, [, b]) => sum + b, 0) / sample.length;
  // GeoJSON: [lon, lat]. Для РФ обычно lat > lon. Если avg0 > avg1 — вероятно [lat, lon] в файле.
  return avg0 > 40 && avg1 > 40 && avg0 > avg1;
}

/** GeoJSON → ymaps [lat, lon]. */
export function geometryToYandexCoords(geometry: RouteGeometry): number[][] {
  const swap = shouldSwapGeoJsonCoords(geometry.coordinates);
  return geometry.coordinates
    .map(([a, b]) => (swap ? [a, b] : [b, a]) as [number, number])
    .filter(([lat, lon]) => isValidCoord(lat, lon));
}

function isValidCoord(lat: number, lon: number): boolean {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return false;
  }
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) {
    return false;
  }
  if (Math.abs(lat) < 0.05 && Math.abs(lon) < 0.05) {
    return false;
  }
  return true;
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

/** Убирает выбросы OSRM-линии далеко от остановок. */
export function filterLineNearStops(
  lineCoords: number[][],
  stops: MapRoutePoint[],
  maxKm = 120,
): number[][] {
  if (lineCoords.length === 0) {
    return lineCoords;
  }
  if (stops.length === 0) {
    return lineCoords;
  }
  const centerLat = stops.reduce((sum, p) => sum + p.lat, 0) / stops.length;
  const centerLon = stops.reduce((sum, p) => sum + p.lon, 0) / stops.length;
  const maxMeters = maxKm * 1000;
  const filtered = lineCoords.filter(
    ([lat, lon]) => haversineMeters(centerLat, centerLon, lat, lon) <= maxMeters,
  );
  return filtered.length >= 2 ? filtered : lineCoords;
}

export function boundsFromYandexCoords(coords: number[][]): [number, number][] | null {
  const valid = coords.filter(([lat, lon]) => isValidCoord(lat, lon));
  if (valid.length === 0) {
    return null;
  }
  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLon = Infinity;
  let maxLon = -Infinity;
  for (const [lat, lon] of valid) {
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
    minLon = Math.min(minLon, lon);
    maxLon = Math.max(maxLon, lon);
  }
  return [
    [minLat, minLon],
    [maxLat, maxLon],
  ];
}
