import type { TripRouteCase } from "../api/routeTypes";
import { RouteMapEmbed } from "./RouteMapEmbed";
import { RouteMapLibre } from "./RouteMapLibre";

interface RouteMapViewProps {
  routeCase: TripRouteCase;
  city?: string;
}

function mapProvider(): "yandex" | "maplibre" {
  const raw = (import.meta.env.VITE_MAP_PROVIDER as string | undefined)?.trim().toLowerCase();
  // Текущий прод: iframe Яндекса. MapLibre включаем явно (feature flag).
  if (raw === "maplibre") {
    return "maplibre";
  }
  return "yandex";
}

/**
 * Карта маршрута.
 * По умолчанию — iframe Яндекс.Карт (текущая реализация / фолбек).
 * MapLibre — только при VITE_MAP_PROVIDER=maplibre.
 */
export function RouteMapView({ routeCase, city = "" }: RouteMapViewProps) {
  const provider = mapProvider();

  if (provider === "maplibre") {
    if (!routeCase.maps_route_url && !routeCase.route_geometry) {
      return null;
    }
    return <RouteMapLibre routeCase={routeCase} city={city} />;
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
