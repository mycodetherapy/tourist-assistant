import type { TripRouteCase } from "../api/routeTypes";
import { mapsUrlToFrameRouteUrl } from "./yandexMapsFrame";

const WIDGET_ORIGIN = "https://yandex.ru/map-widget/v1/";

function applyRouteWidgetDefaults(params: URLSearchParams): void {
  if (!params.has("rtext")) {
    return;
  }
  if (!params.has("mode")) {
    params.set("mode", "routes");
  }
  const rtt = params.get("rtt");
  if (!rtt || rtt === "auto") {
    params.set("rtt", "pd");
  }
}

export function mapsUrlToWidgetUrl(mapsRouteUrl: string): string | null {
  const trimmed = mapsRouteUrl.trim();
  if (!trimmed) {
    return null;
  }
  try {
    const source = new URL(trimmed);
    if (!source.hostname.includes("yandex.")) {
      return null;
    }
    const widget = new URL(WIDGET_ORIGIN);
    source.searchParams.forEach((value, key) => {
      widget.searchParams.set(key, value);
    });
    applyRouteWidgetDefaults(widget.searchParams);
    if (!widget.searchParams.has("rtext") && !widget.searchParams.has("pt") && !widget.searchParams.has("text")) {
      return null;
    }
    return widget.toString();
  } catch {
    return null;
  }
}

export function mapsRouteOpenUrl(mapsRouteUrl: string, city = ""): string | null {
  return mapsUrlToFrameRouteUrl(mapsRouteUrl, city);
}

export function mapsRouteOpenUrlForCase(routeCase: TripRouteCase, city = ""): string | null {
  return mapsUrlToFrameRouteUrl(routeCase.maps_route_url, city);
}

/** Виджет только с метками (без сплошной линии маршрута Яндекса). */
export function buildMarkerWidgetUrl(points: { lat: number; lon: number }[]): string | null {
  if (points.length === 0) {
    return null;
  }
  const widget = new URL(WIDGET_ORIGIN);
  const pt = points.map((p) => `${p.lon},${p.lat},pm2bm`).join("~");
  widget.searchParams.set("pt", pt);
  const first = points[0];
  widget.searchParams.set("ll", `${first.lon},${first.lat}`);
  widget.searchParams.set("z", "14");
  return widget.toString();
}

export function widgetUrlWithUserLocation(widgetUrl: string, lat: number, lon: number): string {
  const url = new URL(widgetUrl);
  url.searchParams.set("pt", `${lon},${lat},pm2rdm`);
  return url.toString();
}

export function isMobileUserAgent(): boolean {
  if (typeof navigator === "undefined") {
    return false;
  }
  return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
}
