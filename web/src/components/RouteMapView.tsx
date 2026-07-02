import type { TripRouteCase } from "../api/routeTypes";
import { hasInteractiveRouteGeometry } from "../utils/routeMapGeometry";
import { RouteMapEmbed } from "./RouteMapEmbed";
import { RouteMapYandex } from "./RouteMapYandex";

interface RouteMapViewProps {
  routeCase: TripRouteCase;
  city?: string;
}

/** Сохранённая геометрия → ymaps + Polyline; иначе iframe-виджет Яндекса. */
export function RouteMapView({ routeCase, city = "" }: RouteMapViewProps) {
  if (!routeCase.maps_route_url) {
    return null;
  }

  if (hasInteractiveRouteGeometry(routeCase)) {
    return <RouteMapYandex routeCase={routeCase} city={city} />;
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
