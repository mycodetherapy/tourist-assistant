import { mapsUrlToWidgetUrl } from "../utils/yandexMap";

interface RouteMapEmbedProps {
  mapsRouteUrl: string;
  caseId?: string;
  title?: string;
}

export function RouteMapEmbed({ mapsRouteUrl, caseId, title }: RouteMapEmbedProps) {
  const widgetUrl = mapsUrlToWidgetUrl(mapsRouteUrl);
  if (!widgetUrl) {
    return null;
  }

  const iframeTitle = title?.trim() || (caseId ? `Маршрут ${caseId}` : "Маршрут на карте");

  return (
    <div className="route-map-embed mb-2 overflow-visible border border-gray-200 bg-gray-50 sm:overflow-hidden sm:rounded-lg">
      <iframe
        src={widgetUrl}
        title={iframeTitle}
        className="route-map-iframe w-full border-0"
        loading="lazy"
        allowFullScreen
        referrerPolicy="no-referrer-when-downgrade"
      />
    </div>
  );
}
