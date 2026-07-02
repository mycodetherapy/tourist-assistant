import type { RefObject } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { MapRoutePoint } from "../utils/mapsRoutePoints";
import { distanceMeters } from "../utils/mapsRoutePoints";
import type { YMapInstance } from "../utils/yandexMapsLoader";
import { loadYandexMaps } from "../utils/yandexMapsLoader";
import {
  GeolocationError,
  geolocationUnavailableMessage,
  watchUserLocation,
} from "../utils/userGeolocation";

export interface MapPoint {
  lat: number;
  lon: number;
}

const STOP_REACHED_M = 45;

function orderedStops(routeStops: MapRoutePoint[]): MapRoutePoint[] {
  return routeStops.filter((point) => Number.isFinite(point.lat) && Number.isFinite(point.lon));
}

export function useRouteMapTracking(
  mapRef: RefObject<YMapInstance | null>,
  mapReadyRef: RefObject<boolean>,
  routeStops: MapRoutePoint[] = [],
) {
  const userLocationPlacemarkRef = useRef<unknown>(null);
  const stopWatchRef = useRef<(() => void) | null>(null);
  const visitedStopIndexRef = useRef(-1);
  const [tracking, setTracking] = useState(false);
  const [locatingUser, setLocatingUser] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [nextStopDistanceM, setNextStopDistanceM] = useState<number | null>(null);
  const [nextStopIndex, setNextStopIndex] = useState<number | null>(null);

  const stops = orderedStops(routeStops);

  const removeUserPlacemark = useCallback(async () => {
    const map = mapRef.current;
    if (!map || !userLocationPlacemarkRef.current) {
      userLocationPlacemarkRef.current = null;
      return;
    }
    map.geoObjects.remove(userLocationPlacemarkRef.current);
    userLocationPlacemarkRef.current = null;
  }, [mapRef]);

  const updateNextStop = useCallback(
    (user: MapPoint) => {
      if (stops.length === 0) {
        setNextStopDistanceM(null);
        setNextStopIndex(null);
        return;
      }
      let visited = visitedStopIndexRef.current;
      while (visited + 1 < stops.length) {
        const candidate = stops[visited + 1];
        if (distanceMeters(user, candidate) <= STOP_REACHED_M) {
          visited += 1;
          visitedStopIndexRef.current = visited;
        } else {
          break;
        }
      }
      const nextIdx = Math.min(visited + 1, stops.length - 1);
      const next = stops[nextIdx];
      setNextStopIndex(nextIdx);
      setNextStopDistanceM(Math.round(distanceMeters(user, next)));
    },
    [stops],
  );

  const showUserLocation = useCallback(
    async (point: MapPoint) => {
      const map = mapRef.current;
      if (!map || !mapReadyRef.current) {
        return;
      }
      const ymaps = await loadYandexMaps();
      if (userLocationPlacemarkRef.current) {
        map.geoObjects.remove(userLocationPlacemarkRef.current);
        userLocationPlacemarkRef.current = null;
      }
      const mark = new ymaps.Placemark(
        [point.lat, point.lon],
        {
          hintContent: "Вы здесь",
          balloonContent: "Ваше текущее местоположение",
        },
        { preset: "islands#blueCircleDotIcon" },
      );
      userLocationPlacemarkRef.current = mark;
      map.geoObjects.add(mark);
      map.setCenter([point.lat, point.lon], map.getZoom());
      updateNextStop(point);
    },
    [mapRef, mapReadyRef, updateNextStop],
  );

  const stopTracking = useCallback(() => {
    stopWatchRef.current?.();
    stopWatchRef.current = null;
    setTracking(false);
    setLocatingUser(false);
    setNextStopDistanceM(null);
    setNextStopIndex(null);
    visitedStopIndexRef.current = -1;
    void removeUserPlacemark();
  }, [removeUserPlacemark]);

  const startTracking = useCallback(() => {
    const unavailable = geolocationUnavailableMessage();
    if (unavailable) {
      setGeoError(unavailable);
      return;
    }

    setGeoError(null);
    setLocatingUser(true);
    setTracking(true);
    visitedStopIndexRef.current = -1;

    stopWatchRef.current?.();
    stopWatchRef.current = watchUserLocation(
      (point) => {
        setLocatingUser(false);
        void showUserLocation(point);
      },
      (error) => {
        setLocatingUser(false);
        setTracking(false);
        stopWatchRef.current = null;
        void removeUserPlacemark();
        const description =
          error instanceof GeolocationError
            ? error.message
            : "Не удалось определить местоположение";
        setGeoError(description);
      },
    );
  }, [removeUserPlacemark, showUserLocation]);

  const toggleTracking = useCallback(() => {
    if (tracking) {
      stopTracking();
      return;
    }
    startTracking();
  }, [startTracking, stopTracking, tracking]);

  useEffect(() => {
    visitedStopIndexRef.current = -1;
    setNextStopDistanceM(null);
    setNextStopIndex(null);
  }, [stops]);

  useEffect(() => {
    return () => {
      stopWatchRef.current?.();
      stopWatchRef.current = null;
    };
  }, []);

  return {
    tracking,
    locatingUser,
    geoError,
    setGeoError,
    toggleTracking,
    stopTracking,
    nextStopDistanceM,
    nextStopIndex,
  };
}
