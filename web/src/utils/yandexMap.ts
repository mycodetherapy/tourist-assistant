/** Конвертация deep link Яндекс.Карт в URL встраиваемого виджета. */

const WIDGET_ORIGIN = "https://yandex.ru/map-widget/v1/";

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
    if (!widget.searchParams.has("rtext") && !widget.searchParams.has("pt") && !widget.searchParams.has("text")) {
      return null;
    }
    return widget.toString();
  } catch {
    return null;
  }
}
