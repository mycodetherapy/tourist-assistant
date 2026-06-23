import { YandexMapRouteOpenLink } from "./YandexMapRouteOpenLink";

interface RouteMapYandexOpenChromeProps {
  mapsRouteUrl: string;
  city?: string;
  /** Закрыть клики по штатной кнопке виджета Яндекса (iframe). */
  maskWidgetFooter?: boolean;
}

/** Единственная кнопка «Открыть в Картах» — внизу слева на карте. */
export function RouteMapYandexOpenChrome({
  mapsRouteUrl,
  city = "",
  maskWidgetFooter = false,
}: RouteMapYandexOpenChromeProps) {
  if (!mapsRouteUrl.trim()) {
    return null;
  }

  return (
    <>
      {maskWidgetFooter ? <div className="yandex-map-footer-mask" aria-hidden /> : null}
      <YandexMapRouteOpenLink
        mapsRouteUrl={mapsRouteUrl}
        city={city}
        overlay
        label="Открыть в Яндекс Картах"
      />
    </>
  );
}
