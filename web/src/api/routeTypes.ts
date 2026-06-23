/** Структурированные маршруты из program.routes (models/routes.py). */

export type RouteCaseId = "A" | "B" | "C" | string;

export interface RouteStop {
  order: number;
  kind: "leisure" | "dining" | "transit_note" | string;
  poi_id?: string | null;
  time_hint?: string;
  narrative?: string;
}

export interface RouteGeometry {
  type: "LineString";
  coordinates: [number, number][];
}

export interface GeoPoint {
  lat: number;
  lon: number;
}

export interface TripRouteCase {
  case_id: RouteCaseId | string;
  title: string;
  summary: string;
  stops: RouteStop[];
  maps_route_url: string;
  preserved?: boolean;
  route_geometry?: RouteGeometry | null;
  route_distance_m?: number | null;
  route_duration_s?: number | null;
  route_map_anchor?: GeoPoint | null;
  route_map_leisure_coords?: GeoPoint[];
}

export interface RouteProgram {
  schema_version?: number;
  materials_summary?: string;
  cases: TripRouteCase[];
}

const CASE_ORDER: Record<string, number> = {
  A: 0,
  B: 1,
  C: 2,
  "N-A": 10,
  "N-B": 11,
  "N-C": 12,
};

function sortKey(item: TripRouteCase): number {
  if (item.preserved) {
    return CASE_ORDER[item.case_id] ?? 0;
  }
  return 100 + (CASE_ORDER[item.case_id] ?? 50);
}

/** Порядок как в SQLite / API (для голосов). */
export function rawRouteCases(routes: unknown): TripRouteCase[] {
  if (!routes || typeof routes !== "object") {
    return [];
  }
  const cases = (routes as RouteProgram).cases;
  if (!Array.isArray(cases)) {
    return [];
  }
  return cases.filter(
    (item): item is TripRouteCase =>
      Boolean(item) &&
      typeof item === "object" &&
      typeof (item as TripRouteCase).case_id === "string",
  );
}

export function parseRouteProgram(routes: unknown): TripRouteCase[] {
  if (!routes || typeof routes !== "object") {
    return [];
  }
  const cases = (routes as RouteProgram).cases;
  if (!Array.isArray(cases)) {
    return [];
  }
  return cases
    .filter(
      (item): item is TripRouteCase =>
        Boolean(item) &&
        typeof item === "object" &&
        typeof (item as TripRouteCase).case_id === "string",
    )
    .sort((a, b) => sortKey(a) - sortKey(b));
}

export function routeCaseAtIndex(
  cases: TripRouteCase[],
  index: number,
): TripRouteCase | undefined {
  return cases[index];
}
