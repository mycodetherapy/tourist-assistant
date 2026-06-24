import type { TripRouteCase } from "../api/routeTypes";
import { hasInteractiveRouteGeometry } from "../utils/routeMapGeometry";
import { RouteMapEmbed } from "./RouteMapEmbed";
import { RouteMapInteractive } from "./RouteMapInteractive";

interface RouteMapViewProps {
  routeCase: TripRouteCase;
  city?: string;
}

/** OSRM-линия на ymaps.Map; без OSRM — iframe-виджет Яндекса с пешим маршрутом. */
export function RouteMapView({ routeCase, city = "" }: RouteMapViewProps) {
  if (!routeCase.maps_route_url) {
    return null;
  }

  if (hasInteractiveRouteGeometry(routeCase)) {
    return <RouteMapInteractive routeCase={routeCase} city={city} />;
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
