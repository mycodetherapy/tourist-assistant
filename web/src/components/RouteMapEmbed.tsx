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
    <div className="mb-2 overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
      <iframe
        src={widgetUrl}
        title={iframeTitle}
        className="h-[min(360px,50vh)] w-full border-0"
        loading="lazy"
        allowFullScreen
        referrerPolicy="no-referrer-when-downgrade"
      />
    </div>
  );
}
