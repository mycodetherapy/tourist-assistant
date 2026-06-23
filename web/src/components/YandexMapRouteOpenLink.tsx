import { useMemo } from "react";
import { mapsUrlToFrameRouteUrl } from "../utils/yandexMapsFrame";

interface YandexMapRouteOpenLinkProps {
  mapsRouteUrl: string;
  city?: string;
  label?: string;
  className?: string;
  /** Кнопка поверх карты (как в виджете Яндекса). */
  overlay?: boolean;
}

/** Единая ссылка «Открыть маршрут в Яндекс.Картах» (формат from=mapframe). */
export function YandexMapRouteOpenLink({
  mapsRouteUrl,
  city = "",
  label = "Открыть маршрут в Яндекс.Картах",
  className,
  overlay = false,
}: YandexMapRouteOpenLinkProps) {
  const href = useMemo(
    () => mapsUrlToFrameRouteUrl(mapsRouteUrl, city),
    [mapsRouteUrl, city],
  );

  if (!href) {
    return null;
  }

  const classes = overlay
    ? `yandex-map-open-overlay ${className ?? ""}`.trim()
    : (className ?? "text-blue-600 underline");

  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={classes}>
      {label}
    </a>
  );
}
