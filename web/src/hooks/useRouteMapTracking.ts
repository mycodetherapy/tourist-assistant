import type { RefObject } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
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

export function useRouteMapTracking(
  mapRef: RefObject<YMapInstance | null>,
  mapReadyRef: RefObject<boolean>,
) {
  const userLocationPlacemarkRef = useRef<unknown>(null);
  const stopWatchRef = useRef<(() => void) | null>(null);
  const [tracking, setTracking] = useState(false);
  const [locatingUser, setLocatingUser] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);

  const removeUserPlacemark = useCallback(async () => {
    const map = mapRef.current;
    if (!map || !userLocationPlacemarkRef.current) {
      userLocationPlacemarkRef.current = null;
      return;
    }
    map.geoObjects.remove(userLocationPlacemarkRef.current);
    userLocationPlacemarkRef.current = null;
  }, [mapRef]);

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
    },
    [mapRef, mapReadyRef],
  );

  const stopTracking = useCallback(() => {
    stopWatchRef.current?.();
    stopWatchRef.current = null;
    setTracking(false);
    setLocatingUser(false);
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
  };
}
