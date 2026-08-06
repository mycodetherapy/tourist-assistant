import "maplibre-gl/dist/maplibre-gl.css";

import maplibregl, { type GeoJSONSource, type Map as MapLibreMap, type Marker } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import type { TripRouteCase } from "../api/routeTypes";
import {
  parseMapsRoutePoints,
  resolveRouteMapMarkers,
  type MapRoutePoint,
} from "../utils/mapsRoutePoints";
import {
  GeolocationError,
  geolocationUnavailableMessage,
  watchUserLocation,
} from "../utils/userGeolocation";
import { MapGeolocationButton } from "./MapGeolocationButton";
import { RouteMapYandexOpenChrome } from "./RouteMapYandexOpenChrome";

const OPENFREEMAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

interface RouteMapLibreProps {
  routeCase: TripRouteCase;
  city?: string;
  onStopClick?: (index: number, point: MapRoutePoint) => void;
}

function lineCoordinates(routeCase: TripRouteCase): [number, number][] {
  const geom = routeCase.route_geometry?.coordinates;
  if (Array.isArray(geom) && geom.length >= 2) {
    const out: [number, number][] = [];
    for (const pair of geom) {
      if (!Array.isArray(pair) || pair.length < 2) {
        continue;
      }
      const lon = Number(pair[0]);
      const lat = Number(pair[1]);
      if (Number.isFinite(lon) && Number.isFinite(lat)) {
        out.push([lon, lat]);
      }
    }
    if (out.length >= 2) {
      return out;
    }
  }

  const fromUrl = parseMapsRoutePoints(routeCase.maps_route_url);
  if (fromUrl.length >= 2) {
    return fromUrl.map((p) => [p.lon, p.lat]);
  }

  const leisure = routeCase.route_map_leisure_coords ?? [];
  const pts: MapRoutePoint[] = [];
  if (routeCase.route_map_anchor) {
    pts.push(routeCase.route_map_anchor);
  }
  for (const p of leisure) {
    pts.push(p);
  }
  return pts.map((p) => [p.lon, p.lat]);
}

function boundsFromCoords(coords: [number, number][]): maplibregl.LngLatBoundsLike | null {
  if (coords.length === 0) {
    return null;
  }
  const bounds = new maplibregl.LngLatBounds(coords[0], coords[0]);
  for (const c of coords) {
    bounds.extend(c);
  }
  return bounds;
}

/** Интерактивная карта маршрута: линия (OSRM или прямые), маркеры, follow GPS. */
export function RouteMapLibre({ routeCase, city = "", onStopClick }: RouteMapLibreProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const userMarkerRef = useRef<Marker | null>(null);
  const stopMarkersRef = useRef<Marker[]>([]);
  const followRef = useRef(false);
  const stopWatchRef = useRef<(() => void) | null>(null);

  const [mapReady, setMapReady] = useState(false);
  const [follow, setFollow] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);

  const lineCoords = useMemo(() => lineCoordinates(routeCase), [routeCase]);
  const hasOsrmGeometry = useMemo(() => {
    const geom = routeCase.route_geometry?.coordinates;
    return Array.isArray(geom) && geom.length >= 2;
  }, [routeCase.route_geometry]);
  const markers = useMemo(() => {
    const routePoints = parseMapsRoutePoints(routeCase.maps_route_url);
    const leisureCount =
      routeCase.route_map_leisure_coords?.length ||
      routeCase.stops.filter((s) => s.kind === "leisure").length;
    return resolveRouteMapMarkers(routePoints, leisureCount, {
      anchor: routeCase.route_map_anchor,
      leisureCoords: routeCase.route_map_leisure_coords,
    });
  }, [routeCase]);

  useEffect(() => {
    followRef.current = follow;
  }, [follow]);

  useEffect(() => {
    if (!containerRef.current || lineCoords.length === 0) {
      return undefined;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OPENFREEMAP_STYLE,
      center: lineCoords[0],
      zoom: 13,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;

    map.on("load", () => {
      map.addSource("route", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: { type: "LineString", coordinates: lineCoords },
        },
      });
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": "#0369a1", "line-width": 4, "line-opacity": 0.9 },
      });

      const bounds = boundsFromCoords(lineCoords);
      if (bounds) {
        map.fitBounds(bounds, { padding: 48, maxZoom: 15, duration: 0 });
      }
      setMapReady(true);
    });

    return () => {
      stopWatchRef.current?.();
      stopWatchRef.current = null;
      for (const marker of stopMarkersRef.current) {
        marker.remove();
      }
      stopMarkersRef.current = [];
      userMarkerRef.current?.remove();
      userMarkerRef.current = null;
      map.remove();
      mapRef.current = null;
      setMapReady(false);
    };
    // Карта создаётся один раз на смену case; линия обновляется отдельным эффектом.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeCase.case_id, routeCase.maps_route_url]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) {
      return;
    }
    const source = map.getSource("route") as GeoJSONSource | undefined;
    source?.setData({
      type: "Feature",
      properties: {},
      geometry: { type: "LineString", coordinates: lineCoords },
    });
    const bounds = boundsFromCoords(lineCoords);
    if (bounds && !followRef.current) {
      map.fitBounds(bounds, { padding: 48, maxZoom: 15, duration: 400 });
    }
  }, [lineCoords, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) {
      return;
    }
    for (const marker of stopMarkersRef.current) {
      marker.remove();
    }
    stopMarkersRef.current = [];

    if (markers.anchor) {
      const el = document.createElement("div");
      el.className = "route-map-marker route-map-marker--anchor";
      el.title = "Старт";
      el.textContent = "S";
      stopMarkersRef.current.push(
        new maplibregl.Marker({ element: el }).setLngLat([markers.anchor.lon, markers.anchor.lat]).addTo(map),
      );
    }

    markers.leisureStops.forEach((point, index) => {
      const el = document.createElement("button");
      el.type = "button";
      el.className = "route-map-marker route-map-marker--stop";
      el.textContent = String(index + 1);
      el.title = `Остановка ${index + 1}`;
      el.addEventListener("click", (event) => {
        event.stopPropagation();
        onStopClick?.(index, point);
      });
      stopMarkersRef.current.push(
        new maplibregl.Marker({ element: el }).setLngLat([point.lon, point.lat]).addTo(map),
      );
    });
  }, [markers, mapReady, onStopClick]);

  useEffect(() => {
    if (!follow) {
      stopWatchRef.current?.();
      stopWatchRef.current = null;
      return undefined;
    }

    const unavailable = geolocationUnavailableMessage();
    if (unavailable) {
      setGeoError(unavailable);
      setFollow(false);
      return undefined;
    }

    setGeoError(null);
    stopWatchRef.current = watchUserLocation(
      (point) => {
        const map = mapRef.current;
        if (!map) {
          return;
        }
        if (!userMarkerRef.current) {
          const el = document.createElement("div");
          el.className = "route-map-marker route-map-marker--user";
          el.title = "Вы здесь";
          userMarkerRef.current = new maplibregl.Marker({ element: el })
            .setLngLat([point.lon, point.lat])
            .addTo(map);
        } else {
          userMarkerRef.current.setLngLat([point.lon, point.lat]);
        }
        if (followRef.current) {
          map.easeTo({ center: [point.lon, point.lat], duration: 500, zoom: Math.max(map.getZoom(), 15) });
        }
      },
      (error: GeolocationError) => {
        setGeoError(error.message);
        setFollow(false);
      },
    );

    return () => {
      stopWatchRef.current?.();
      stopWatchRef.current = null;
    };
  }, [follow]);

  if (lineCoords.length === 0 && !routeCase.maps_route_url.trim()) {
    return null;
  }

  return (
    <div className="route-map-embed mb-2 rounded-lg border border-gray-200 bg-gray-50">
      <div
        className="route-map-scroll relative"
        onTouchStart={(event) => event.stopPropagation()}
        onTouchMove={(event) => event.stopPropagation()}
      >
        <div ref={containerRef} className="route-map-canvas" />
        <MapGeolocationButton
          locating={false}
          active={follow}
          topClassName="top-2"
          onClick={() => setFollow((value) => !value)}
        />
        {geoError ? (
          <div className="absolute inset-x-2 bottom-14 z-[5] rounded bg-white/95 px-2 py-1 text-xs text-amber-800 shadow">
            {geoError}
          </div>
        ) : null}
        {!hasOsrmGeometry ? (
          <div className="pointer-events-none absolute inset-x-2 top-2 z-[4] max-w-[70%] rounded bg-white/90 px-2 py-1 text-[11px] text-slate-600 shadow">
            Линия приближённая (нет OSRM-геометрии)
          </div>
        ) : null}
        <RouteMapYandexOpenChrome mapsRouteUrl={routeCase.maps_route_url} city={city} />
      </div>
    </div>
  );
}
