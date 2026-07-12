import type { TripRouteCase } from "../api/routeTypes";
import { RouteMapEmbed } from "./RouteMapEmbed";

interface RouteMapViewProps {
  routeCase: TripRouteCase;
  city?: string;
}

/** Маршрут на карте — iframe-виджет Яндекс.Карт. */
export function RouteMapView({ routeCase, city = "" }: RouteMapViewProps) {
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
