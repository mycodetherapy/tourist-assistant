import { YandexMapRouteOpenLink } from "./YandexMapRouteOpenLink";

interface RouteMapYandexOpenChromeProps {
  mapsRouteUrl: string;
  city?: string;
}

/** Иконка «Открыть в Яндекс Картах» — только поверх MapLibre (OSRM), не на iframe-виджете. */
export function RouteMapYandexOpenChrome({
  mapsRouteUrl,
  city = "",
}: RouteMapYandexOpenChromeProps) {
  if (!mapsRouteUrl.trim()) {
    return null;
  }

  return (
    <YandexMapRouteOpenLink
      mapsRouteUrl={mapsRouteUrl}
      city={city}
      overlay
      iconOnly
      label="Открыть в Яндекс Картах"
    />
  );
}
