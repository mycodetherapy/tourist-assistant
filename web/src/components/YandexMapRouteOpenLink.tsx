import { useMemo } from "react";
import yandexMapsPin from "../assets/yandex-maps-pin.svg";
import { mapsUrlToFrameRouteUrl } from "../utils/yandexMapsFrame";

interface YandexMapRouteOpenLinkProps {
  mapsRouteUrl: string;
  city?: string;
  label?: string;
  className?: string;
  /** Кнопка поверх карты (как в виджете Яндекса). */
  overlay?: boolean;
  /** Иконка вместо текста (для overlay). */
  iconOnly?: boolean;
}

/** Единая ссылка «Открыть маршрут в Яндекс.Картах» (формат from=mapframe). */
export function YandexMapRouteOpenLink({
  mapsRouteUrl,
  city = "",
  label = "Открыть маршрут в Яндекс.Картах",
  className,
  overlay = false,
  iconOnly = false,
}: YandexMapRouteOpenLinkProps) {
  const href = useMemo(
    () => mapsUrlToFrameRouteUrl(mapsRouteUrl, city),
    [mapsRouteUrl, city],
  );

  if (!href) {
    return null;
  }

  const useIcon = overlay && iconOnly;
  const classes = overlay
    ? `yandex-map-open-overlay${useIcon ? " yandex-map-open-overlay--icon" : ""} ${className ?? ""}`.trim()
    : (className ?? "text-blue-600 underline");

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={classes}
      aria-label={useIcon ? label : undefined}
      title={useIcon ? label : undefined}
    >
      {useIcon ? (
        <img src={yandexMapsPin} alt="" width={22} height={22} decoding="async" />
      ) : (
        label
      )}
    </a>
  );
}
