/** Структурированные маршруты из program.routes (models/routes.py). */

export type RouteCaseId = "A" | "B" | "C" | string;

export interface RouteStop {
  order: number;
  kind: "leisure" | "dining" | "transit_note" | string;
  poi_id?: string | null;
  time_hint?: string;
  narrative?: string;
}

export interface TripRouteCase {
  case_id: RouteCaseId | string;
  title: string;
  summary: string;
  stops: RouteStop[];
  maps_route_url: string;
  preserved?: boolean;
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
