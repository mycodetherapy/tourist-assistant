import { Spin } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { mapsUrlToWidgetUrl } from "../utils/yandexMap";
import { RouteMapYandexOpenChrome } from "./RouteMapYandexOpenChrome";

interface RouteMapEmbedProps {
  mapsRouteUrl: string;
  city?: string;
  caseId?: string;
  title?: string;
}

export function RouteMapEmbed({
  mapsRouteUrl,
  city = "",
  caseId,
  title,
}: RouteMapEmbedProps) {
  const iframeTitle = title?.trim() || (caseId ? `Маршрут ${caseId}` : "Маршрут на карте");
  const iframeSrc = useMemo(() => mapsUrlToWidgetUrl(mapsRouteUrl), [mapsRouteUrl]);
  const [iframeLoading, setIframeLoading] = useState(true);

  useEffect(() => {
    setIframeLoading(true);
  }, [iframeSrc]);

  useEffect(() => {
    if (!iframeLoading) {
      return undefined;
    }
    const safetyTimer = window.setTimeout(() => setIframeLoading(false), 15_000);
    return () => window.clearTimeout(safetyTimer);
  }, [iframeLoading, iframeSrc]);

  const handleIframeLoad = useCallback(() => {
    setIframeLoading(false);
  }, []);

  if (!iframeSrc) {
    return null;
  }

  return (
    <div className="route-map-embed mb-2 rounded-lg border border-gray-200 bg-gray-50">
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
          onLoad={handleIframeLoad}
        />
        {iframeLoading ? (
          <div
            className="absolute inset-0 z-[12] flex items-center justify-center bg-gray-50/90"
            aria-live="polite"
            aria-busy="true"
          >
            <Spin description="Загрузка карты…" />
          </div>
        ) : null}
        <RouteMapYandexOpenChrome
          mapsRouteUrl={mapsRouteUrl}
          city={city}
          maskWidgetFooter
        />
      </div>
    </div>
  );
}
