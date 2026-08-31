import type { ItineraryVersion } from "../repos/trips.js";
import {
  getCityPackEntry,
  getOsrmGraphUpdatedAt,
  resolveCitySlug,
} from "./osrmReadyCities.js";

export type TripOsrmUpdateStatus = {
  slug: string | null;
  display_name: string | null;
  osrm_ready: boolean;
  osrm_updated_at: string | null;
  routes_built_at: string | null;
  /** Граф новее последней сборки маршрутов — предложить пересбор. */
  update_available: boolean;
};

function programHasRoutes(program: Record<string, unknown> | null | undefined): boolean {
  if (!program || typeof program !== "object") return false;
  const routes = program.routes as Record<string, unknown> | string | null | undefined;
  if (!routes) return false;
  if (typeof routes === "string") return routes.trim().length > 0;
  if (typeof routes === "object") {
    const cases = (routes as { cases?: unknown }).cases;
    if (Array.isArray(cases) && cases.length > 0) return true;
    // structured ProgramSection
    const items = (routes as { items?: unknown }).items;
    if (Array.isArray(items) && items.length > 0) return true;
  }
  return false;
}

export function buildTripOsrmUpdateStatus(params: {
  city: string;
  latest: ItineraryVersion | null;
}): TripOsrmUpdateStatus {
  const slug = resolveCitySlug(params.city);
  const entry = slug ? getCityPackEntry(slug) : null;
  const osrmUpdatedAt = slug ? getOsrmGraphUpdatedAt(slug) : null;
  const hasRoutes = programHasRoutes(params.latest?.program ?? null);
  const routesBuiltAt = hasRoutes ? params.latest?.created_at ?? null : null;

  let updateAvailable = false;
  if (slug && osrmUpdatedAt && routesBuiltAt) {
    const graphMs = Date.parse(osrmUpdatedAt);
    const builtMs = Date.parse(routesBuiltAt);
    if (Number.isFinite(graphMs) && Number.isFinite(builtMs) && graphMs > builtMs) {
      updateAvailable = true;
    }
  }

  return {
    slug,
    display_name: entry?.display_name ?? null,
    osrm_ready: Boolean(osrmUpdatedAt),
    osrm_updated_at: osrmUpdatedAt,
    routes_built_at: routesBuiltAt,
    update_available: updateAvailable,
  };
}
