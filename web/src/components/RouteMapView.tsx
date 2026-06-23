import type { TripRouteCase } from "../api/routeTypes";
import { hasInteractiveRouteGeometry } from "../utils/routeMapGeometry";
import { parseMapsRoutePoints, resolveRouteMapMarkers } from "../utils/mapsRoutePoints";
import { RouteMapEmbed } from "./RouteMapEmbed";
import { RouteMapInteractive } from "./RouteMapInteractive";

interface RouteMapViewProps {
  routeCase: TripRouteCase;
  city?: string;
}

function leisureStopCount(routeCase: TripRouteCase): number {
  return routeCase.stops.filter((stop) => stop.kind === "leisure").length;
}

/** OSM-линия на ymaps.Map или iframe Яндекса, если геометрии нет. */
export function RouteMapView({ routeCase, city = "" }: RouteMapViewProps) {
  if (!routeCase.maps_route_url) {
    return null;
  }

  if (hasInteractiveRouteGeometry(routeCase)) {
    return <RouteMapInteractive routeCase={routeCase} city={city} />;
  }

  const routePoints = parseMapsRoutePoints(routeCase.maps_route_url);
  const markers = resolveRouteMapMarkers(routePoints, leisureStopCount(routeCase), {
    anchor: routeCase.route_map_anchor,
    leisureCoords: routeCase.route_map_leisure_coords,
  });
  const markerPoints = [
    ...(markers.anchor ? [markers.anchor] : []),
    ...markers.leisureStops,
  ];

  return (
    <RouteMapEmbed
      mapsRouteUrl={routeCase.maps_route_url}
      city={city}
      caseId={routeCase.case_id}
      title={routeCase.title}
      markerPoints={markerPoints}
    />
  );
}
