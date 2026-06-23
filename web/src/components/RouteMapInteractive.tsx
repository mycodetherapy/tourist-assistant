import { Alert, Spin } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import type { TripRouteCase } from "../api/routeTypes";
import { useRouteMapTracking } from "../hooks/useRouteMapTracking";
import { parseMapsRoutePoints, resolveRouteMapMarkers } from "../utils/mapsRoutePoints";
import {
  boundsFromYandexCoords,
  filterLineNearStops,
  geometryToYandexCoords,
} from "../utils/routeMapGeometry";
import { geolocationUnavailableMessage } from "../utils/userGeolocation";
import {
  isYandexMapsConfigured,
  loadYandexMaps,
  type YMapInstance,
} from "../utils/yandexMapsLoader";
import { MapGeolocationButton } from "./MapGeolocationButton";
import { RouteMapYandexOpenChrome } from "./RouteMapYandexOpenChrome";

interface RouteMapInteractiveProps {
  routeCase: TripRouteCase;
  city?: string;
}

const MIN_MAP_ZOOM = 11;
const MAX_MAP_ZOOM = 16;

const ROUTE_POLYLINE_OPTIONS = {
  strokeColor: "#2563eb",
  strokeWidth: 4,
  strokeOpacity: 0.85,
  // «3 2» — длина штриха и пробел в px (чаще при той же длине черточки)
  strokeStyle: "3 2",
} as const;

function leisureStopCount(routeCase: TripRouteCase): number {
  return routeCase.stops.filter((stop) => stop.kind === "leisure").length;
}

function clampMapZoom(map: YMapInstance): void {
  const zoom = map.getZoom();
  if (zoom > MAX_MAP_ZOOM) {
    map.setZoom(MAX_MAP_ZOOM);
  } else if (zoom < MIN_MAP_ZOOM) {
    map.setZoom(MIN_MAP_ZOOM);
  }
}

function fitRouteMapBounds(map: YMapInstance, coords: number[][]): void {
  const bounds = boundsFromYandexCoords(coords);
  if (!bounds) {
    return;
  }
  const [[minLat, minLon], [maxLat, maxLon]] = bounds;
  const latSpan = maxLat - minLat;
  const lonSpan = maxLon - minLon;
  if (latSpan < 0.0008 && lonSpan < 0.0008) {
    map.setCenter([(minLat + maxLat) / 2, (minLon + maxLon) / 2], 15);
    return;
  }
  map.setBounds(bounds, { checkZoomRange: true, zoomMargin: 48 });
  window.setTimeout(() => clampMapZoom(map), 50);
}

export function RouteMapInteractive({
  routeCase,
  city = "",
}: RouteMapInteractiveProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<YMapInstance | null>(null);
  const mapReadyRef = useRef(false);
  const routeObjectsRef = useRef<unknown[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const geometry = routeCase.route_geometry;
  const routePoints = useMemo(
    () => parseMapsRoutePoints(routeCase.maps_route_url),
    [routeCase.maps_route_url],
  );
  const markers = useMemo(
    () =>
      resolveRouteMapMarkers(routePoints, leisureStopCount(routeCase), {
        anchor: routeCase.route_map_anchor,
        leisureCoords: routeCase.route_map_leisure_coords,
      }),
    [
      routePoints,
      routeCase.stops,
      routeCase.route_map_anchor,
      routeCase.route_map_leisure_coords,
    ],
  );
  const lineCoords = useMemo(() => {
    if (!geometry) {
      return [];
    }
    const raw = geometryToYandexCoords(geometry);
    const allStops = [
      ...(markers.anchor ? [markers.anchor] : []),
      ...markers.leisureStops,
    ];
    return filterLineNearStops(raw, allStops);
  }, [geometry, markers]);

  const {
    tracking,
    locatingUser,
    geoError,
    setGeoError,
    toggleTracking,
    stopTracking,
  } = useRouteMapTracking(mapRef, mapReadyRef);

  const stopTrackingRef = useRef(stopTracking);
  stopTrackingRef.current = stopTracking;

  useEffect(() => {
    setGeoError(geolocationUnavailableMessage());
  }, [setGeoError]);

  useEffect(() => {
    if (!isYandexMapsConfigured() || !geometry || lineCoords.length < 2) {
      setError("Нет геометрии маршрута для интерактивной карты");
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    mapReadyRef.current = false;
    stopTrackingRef.current();

    loadYandexMaps()
      .then((ymaps) => {
        if (cancelled || !containerRef.current) {
          return;
        }

        mapRef.current?.destroy();
        routeObjectsRef.current = [];
        stopTrackingRef.current();

        const focusCoords = [
          ...(markers.anchor ? [[markers.anchor.lat, markers.anchor.lon]] : []),
          ...markers.leisureStops.map((p) => [p.lat, p.lon]),
        ];
        const flatLine = lineCoords;
        const center = focusCoords[0] ?? flatLine[0] ?? [55.79, 49.12];

        const map = new ymaps.Map(
          containerRef.current,
          {
            center,
            zoom: 14,
            controls: ["zoomControl"],
          },
          { suppressMapOpenBlock: true },
        );
        mapRef.current = map;
        mapReadyRef.current = true;

        const polyline = new ymaps.Polyline(
          lineCoords,
          {},
          ROUTE_POLYLINE_OPTIONS,
        );
        map.geoObjects.add(polyline);
        routeObjectsRef.current.push(polyline);

        if (markers.anchor) {
          const anchorMark = new ymaps.Placemark(
            [markers.anchor.lat, markers.anchor.lon],
            {
              hintContent: "Старт (базовая точка)",
              balloonContent: "Базовая точка маршрута",
            },
            { preset: "islands#redDotIcon" },
          );
          map.geoObjects.add(anchorMark);
          routeObjectsRef.current.push(anchorMark);
        }

        markers.leisureStops.forEach((point, index) => {
          const mark = new ymaps.Placemark(
            [point.lat, point.lon],
            {
              iconContent: String(index + 1),
              hintContent: `Остановка ${index + 1}`,
            },
            { preset: "islands#blueCircleIcon" },
          );
          map.geoObjects.add(mark);
          routeObjectsRef.current.push(mark);
        });

        const boundsCoords = [...flatLine, ...focusCoords];
        fitRouteMapBounds(map, boundsCoords);

        setLoading(false);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      mapReadyRef.current = false;
      stopTrackingRef.current();
      mapRef.current?.destroy();
      mapRef.current = null;
      routeObjectsRef.current = [];
    };
  }, [geometry, lineCoords, markers, routeCase.case_id]);

  if (!geometry || lineCoords.length < 2) {
    return null;
  }

  const iframeTitle = routeCase.title?.trim() || `Маршрут ${routeCase.case_id}`;

  return (
    <div className="route-map-embed mb-2 rounded-lg border border-gray-200 bg-gray-50">
      {geoError ? (
        <Alert
          type="warning"
          showIcon
          className="!m-2 !mb-0"
          title="Геолокация"
          description={geoError}
          closable
          onClose={() => setGeoError(null)}
        />
      ) : null}
      {error ? (
        <Alert type="error" showIcon className="!m-2 !mb-0" title="Карта" description={error} />
      ) : null}
      <div
        className="route-map-scroll relative"
        onTouchStart={(event) => event.stopPropagation()}
        onTouchMove={(event) => event.stopPropagation()}
      >
        <div
          ref={containerRef}
          className="route-map-canvas w-full"
          role="img"
          aria-label={iframeTitle}
        />
        {loading ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/70">
            <Spin />
          </div>
        ) : null}
        {isYandexMapsConfigured() ? (
          <MapGeolocationButton
            locating={locatingUser}
            active={tracking}
            onClick={toggleTracking}
          />
        ) : null}
        <RouteMapYandexOpenChrome
          mapsRouteUrl={routeCase.maps_route_url}
          city={city}
          maskWidgetFooter
        />
      </div>
      <p className="route-map-attribution px-2 pb-1 text-[10px] leading-tight text-gray-400">
        Маршрут: © OpenStreetMap contributors (ODbL)
        {routeCase.route_distance_m
          ? ` · ~${(routeCase.route_distance_m / 1000).toFixed(1)} км`
          : ""}
      </p>
    </div>
  );
}
