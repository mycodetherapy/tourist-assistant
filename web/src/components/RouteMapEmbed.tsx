import { mapsUrlToWidgetUrl } from "../utils/yandexMap";

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
  const widgetUrl = mapsUrlToWidgetUrl(mapsRouteUrl);
  if (!widgetUrl) {
    return null;
  }

  const iframeTitle = title?.trim() || (caseId ? `Маршрут ${caseId}` : "Маршрут на карте");

  return (
    <div className="route-map-embed mb-2 rounded-lg border border-gray-200 bg-gray-50">
      <div
        className="route-map-scroll"
        onTouchStart={(event) => event.stopPropagation()}
        onTouchMove={(event) => event.stopPropagation()}
      >
        <iframe
          src={widgetUrl}
          title={iframeTitle}
          className="route-map-iframe w-full border-0"
          loading={showMobileLink ? "eager" : "lazy"}
          allowFullScreen
          referrerPolicy="no-referrer-when-downgrade"
        />
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
