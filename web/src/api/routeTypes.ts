/** Структурированные маршруты из program.routes (models/routes.py). */

export type RouteCaseId = "A" | "B" | "C";

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
}

export interface RouteProgram {
  schema_version?: number;
  materials_summary?: string;
  cases: TripRouteCase[];
}

const CASE_ORDER: Record<string, number> = { A: 0, B: 1, C: 2 };

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
    .sort(
      (a, b) =>
        (CASE_ORDER[a.case_id] ?? 99) - (CASE_ORDER[b.case_id] ?? 99),
    );
}

export function routeCaseAtIndex(
  cases: TripRouteCase[],
  index: number,
): TripRouteCase | undefined {
  return cases[index];
}
