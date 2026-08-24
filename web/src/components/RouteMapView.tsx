import { lazy, Suspense } from "react";
import { Spin } from "antd";
import type { TripRouteCase } from "../api/routeTypes";
import type { MapRoutePoint } from "../utils/mapsRoutePoints";
import { RouteMapEmbed } from "./RouteMapEmbed";

const RouteMapLibre = lazy(async () => {
  const mod = await import("./RouteMapLibre");
  return { default: mod.RouteMapLibre };
});

interface RouteMapViewProps {
  routeCase: TripRouteCase;
  city?: string;
  onStopClick?: (index: number, point: MapRoutePoint) => void;
}

function maplibreFlagEnabled(): boolean {
  const raw = (import.meta.env.VITE_MAP_PROVIDER as string | undefined)?.trim().toLowerCase();
  return raw === "maplibre";
}

function hasOsrmGeometry(routeCase: TripRouteCase): boolean {
  const coords = routeCase.route_geometry?.coordinates;
  return Array.isArray(coords) && coords.length >= 2;
}

/**
 * Карта маршрута.
 *
 * - VITE_MAP_PROVIDER=maplibre + есть route_geometry → MapLibre (клики, follow, линия OSRM)
 * - иначе → iframe Яндекса (города без OSRM-графа, Wikidata-only, старые поездки)
 * - без флага maplibre → всегда iframe (прод-фолбек)
 */
export function RouteMapView({ routeCase, city = "", onStopClick }: RouteMapViewProps) {
  const useMapLibre = maplibreFlagEnabled() && hasOsrmGeometry(routeCase);

  if (useMapLibre) {
    return (
      <Suspense
        fallback={
          <div className="route-map-embed mb-2 flex min-h-[240px] items-center justify-center rounded-lg border border-gray-200 bg-gray-50">
            <Spin description="Загрузка карты…" />
          </div>
        }
      >
        <RouteMapLibre routeCase={routeCase} city={city} onStopClick={onStopClick} />
      </Suspense>
    );
  }

  if (!routeCase.maps_route_url) {
    return null;
  }
  return (
    <RouteMapEmbed
      mapsRouteUrl={routeCase.maps_route_url}
      city={city}
      caseId={routeCase.case_id}
      title={routeCase.title}
    />
  );
}
