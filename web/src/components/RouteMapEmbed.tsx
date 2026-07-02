import { DownOutlined, InfoCircleOutlined, UpOutlined } from "@ant-design/icons";
import { Alert } from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  GeolocationError,
  geolocationUnavailableMessage,
  requestUserLocation,
} from "../utils/userGeolocation";
import {
  buildMarkerWidgetUrl,
  mapsUrlToWidgetUrl,
  widgetUrlWithUserLocation,
} from "../utils/yandexMap";
import type { MapRoutePoint } from "../utils/mapsRoutePoints";
import { isYandexMapsConfigured } from "../utils/yandexMapsLoader";
import { MapGeolocationButton } from "./MapGeolocationButton";
import { RouteMapYandexOpenChrome } from "./RouteMapYandexOpenChrome";

interface RouteMapEmbedProps {
  mapsRouteUrl: string;
  city?: string;
  caseId?: string;
  title?: string;
  /** Почему показан резервный виджет (из RouteMapYandex). */
  fallbackReason?: string | null;
  /** Запасной вариант, если из maps_route_url не собрать виджет маршрута. */
  markerPoints?: MapRoutePoint[];
}

export function RouteMapEmbed({
  mapsRouteUrl,
  city = "",
  caseId,
  title,
  fallbackReason,
  markerPoints,
}: RouteMapEmbedProps) {
  const iframeTitle = title?.trim() || (caseId ? `Маршрут ${caseId}` : "Маршрут на карте");
  const baseWidgetUrl = useMemo(() => {
    const routeWidget = mapsUrlToWidgetUrl(mapsRouteUrl);
    if (routeWidget) {
      return routeWidget;
    }
    if (markerPoints && markerPoints.length > 0) {
      return buildMarkerWidgetUrl(markerPoints);
    }
    return null;
  }, [mapsRouteUrl, markerPoints]);

  const [userLocation, setUserLocation] = useState<{ lat: number; lon: number } | null>(null);
  const [locatingUser, setLocatingUser] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [limitedDetailsOpen, setLimitedDetailsOpen] = useState(false);

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

  const limitedModeTitle = "Резервный режим карты";
  const limitedModeDescription =
    "Не удалось загрузить интерактивную карту Яндекса. Показан встроенный виджет — геолокация в реальном времени недоступна.";

  return (
    <div className="route-map-embed mb-2 rounded-lg border border-gray-200 bg-gray-50">
      <div className="mx-2 mt-2 mb-0 overflow-hidden rounded-md border border-blue-200 bg-blue-50/90 text-sm">
        <button
          type="button"
          className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-blue-950"
          onClick={() => setLimitedDetailsOpen((open) => !open)}
          aria-expanded={limitedDetailsOpen}
          aria-controls="route-map-limited-details"
        >
          <InfoCircleOutlined className="shrink-0 text-blue-600" aria-hidden />
          <span className="min-w-0 flex-1 text-sm font-medium leading-snug">
            {limitedModeTitle}
          </span>
          {limitedDetailsOpen ? (
            <UpOutlined className="shrink-0 text-xs text-blue-700/80" aria-hidden />
          ) : (
            <DownOutlined className="shrink-0 text-xs text-blue-700/80" aria-hidden />
          )}
        </button>
        {limitedDetailsOpen ? (
          <p
            id="route-map-limited-details"
            className="border-t border-blue-200/80 px-2.5 pb-2 pt-1.5 text-xs leading-snug text-blue-900/90"
          >
            {limitedModeDescription}
            {fallbackReason ? (
              <>
                {" "}
                <span className="font-medium">Причина:</span> {fallbackReason}
              </>
            ) : null}
          </p>
        ) : null}
      </div>
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
          loading="lazy"
          allowFullScreen
          referrerPolicy="no-referrer-when-downgrade"
          sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-forms"
        />
        <RouteMapYandexOpenChrome
          mapsRouteUrl={mapsRouteUrl}
          city={city}
          maskWidgetFooter
        />
        {isYandexMapsConfigured() ? (
          <MapGeolocationButton
            locating={locatingUser}
            onClick={() => void handleGeolocationClick()}
          />
        ) : null}
      </div>
      <p className="route-map-attribution px-2 pb-1 text-[10px] leading-tight text-gray-400">
        Маршрут: виджет © Яндекс.Карты · резервный режим
      </p>
    </div>
  );
}
