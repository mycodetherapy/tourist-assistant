import { Alert } from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  GeolocationError,
  geolocationUnavailableMessage,
  requestUserLocation,
} from "../utils/userGeolocation";
import { mapsUrlToWidgetUrl, widgetUrlWithUserLocation } from "../utils/yandexMap";
import { isYandexMapsConfigured } from "../utils/yandexMapsLoader";
import { MapGeolocationButton } from "./MapGeolocationButton";

interface RouteMapEmbedProps {
  mapsRouteUrl: string;
  caseId?: string;
  title?: string;
  /** Ссылка «Подробнее» под картой — обход бага iframe на мобильных. */
  showMobileLink?: boolean;
}

export function RouteMapEmbed({
  mapsRouteUrl,
  caseId,
  title,
  showMobileLink = false,
}: RouteMapEmbedProps) {
  const iframeTitle = title?.trim() || (caseId ? `Маршрут ${caseId}` : "Маршрут на карте");
  const baseWidgetUrl = useMemo(() => mapsUrlToWidgetUrl(mapsRouteUrl), [mapsRouteUrl]);

  const [userLocation, setUserLocation] = useState<{ lat: number; lon: number } | null>(null);
  const [locatingUser, setLocatingUser] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);

  const iframeSrc = useMemo(() => {
    if (!baseWidgetUrl) {
      return null;
    }
    if (!userLocation) {
      return baseWidgetUrl;
    }
    return widgetUrlWithUserLocation(baseWidgetUrl, userLocation.lat, userLocation.lon);
  }, [baseWidgetUrl, userLocation]);

  useEffect(() => {
    setGeoError(geolocationUnavailableMessage());
  }, []);

  const handleGeolocationClick = async () => {
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
      setUserLocation(point);
      setGeoError(null);
    } catch (err) {
      const description =
        err instanceof GeolocationError
          ? err.message
          : "Не удалось определить местоположение";
      setGeoError(description);
    } finally {
      window.clearTimeout(safetyTimer);
      setLocatingUser(false);
    }
  };

  if (!iframeSrc) {
    return null;
  }

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
      <div
        className="route-map-scroll relative"
        onTouchStart={(event) => event.stopPropagation()}
        onTouchMove={(event) => event.stopPropagation()}
      >
        <iframe
          key={iframeSrc}
          src={iframeSrc}
          title={iframeTitle}
          className="route-map-iframe w-full border-0"
          loading={showMobileLink ? "eager" : "lazy"}
          allowFullScreen
          referrerPolicy="no-referrer-when-downgrade"
        />
        {isYandexMapsConfigured() ? (
          <MapGeolocationButton
            locating={locatingUser}
            onClick={() => void handleGeolocationClick()}
          />
        ) : null}
      </div>
      {showMobileLink ? (
        <a
          href={mapsRouteUrl}
          target="_blank"
          rel="noreferrer"
          className="route-map-mobile-link"
        >
          Подробнее в Яндекс.Картах
        </a>
      ) : null}
    </div>
  );
}
