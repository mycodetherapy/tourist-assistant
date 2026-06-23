import type { RefObject } from "react";
import { notification } from "antd";
import { useCallback, useRef, useState } from "react";
import type { YMapInstance } from "../utils/yandexMapsLoader";
import { loadYandexMaps } from "../utils/yandexMapsLoader";
import {
  GeolocationError,
  geolocationUnavailableMessage,
  requestUserLocation,
} from "../utils/userGeolocation";

export interface MapPoint {
  lat: number;
  lon: number;
}

export function useYandexMapGeolocation(
  mapRef: RefObject<YMapInstance | null>,
  mapReadyRef: RefObject<boolean>,
) {
  const userLocationPlacemarkRef = useRef<unknown>(null);
  const [locatingUser, setLocatingUser] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);

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
      map.setCenter([point.lat, point.lon], 16);
    },
    [mapRef, mapReadyRef],
  );

  const handleGeolocationClick = useCallback(async () => {
    const unavailable = geolocationUnavailableMessage();
    if (unavailable) {
      setGeoError(unavailable);
      return;
    }

    setGeoError(null);
    setLocatingUser(true);
    const safetyTimer = window.setTimeout(() => {
      setLocatingUser(false);
      setGeoError("Геолокация не отвечает. Проверьте GPS и разрешение для сайта.");
    }, 20_000);

    try {
      const point = await requestUserLocation();
      await showUserLocation(point);
      setGeoError(null);
    } catch (err) {
      const description =
        err instanceof GeolocationError
          ? err.message
          : "Не удалось определить местоположение";
      setGeoError(description);
      notification.warning({ title: "Геолокация", description });
    } finally {
      window.clearTimeout(safetyTimer);
      setLocatingUser(false);
    }
  }, [showUserLocation]);

  const clearUserLocationPlacemark = useCallback(() => {
    userLocationPlacemarkRef.current = null;
  }, []);

  return {
    locatingUser,
    geoError,
    setGeoError,
    handleGeolocationClick,
    clearUserLocationPlacemark,
  };
}
