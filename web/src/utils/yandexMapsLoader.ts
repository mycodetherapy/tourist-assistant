type YMapsApi = {
  ready: (callback: () => void) => void;
  Map: new (
    container: string | HTMLElement,
    state: { center: number[]; zoom: number; controls?: string[] },
    options?: Record<string, unknown>,
  ) => YMapInstance;
  Placemark: new (
    coords: number[],
    properties?: Record<string, unknown>,
    options?: Record<string, unknown>,
  ) => unknown;
};

type YMapInstance = {
  events: { add: (event: string, handler: (event: YMapClickEvent) => void) => void };
  geoObjects: { add: (obj: unknown) => void; remove: (obj: unknown) => void };
  setCenter: (center: number[], zoom?: number) => void;
  destroy: () => void;
};

type YMapClickEvent = {
  get: (key: "coords") => number[];
};

declare global {
  interface Window {
    ymaps?: YMapsApi;
  }
}

let loadPromise: Promise<YMapsApi> | null = null;

export function getYandexMapsApiKey(): string {
  return (import.meta.env.VITE_YANDEX_MAPS_API_KEY as string | undefined)?.trim() ?? "";
}

export function isYandexMapsConfigured(): boolean {
  return getYandexMapsApiKey().length > 0;
}

export function loadYandexMaps(): Promise<YMapsApi> {
  if (window.ymaps) {
    return new Promise((resolve) => {
      window.ymaps!.ready(() => resolve(window.ymaps!));
    });
  }
  if (loadPromise) {
    return loadPromise;
  }
  const apiKey = getYandexMapsApiKey();
  if (!apiKey) {
    return Promise.reject(new Error("VITE_YANDEX_MAPS_API_KEY не задан"));
  }
  loadPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `https://api-maps.yandex.ru/2.1/?apikey=${encodeURIComponent(apiKey)}&lang=ru_RU`;
    script.async = true;
    script.onload = () => {
      if (!window.ymaps) {
        reject(new Error("Yandex Maps API не загрузился"));
        return;
      }
      window.ymaps.ready(() => resolve(window.ymaps!));
    };
    script.onerror = () => reject(new Error("Не удалось загрузить Yandex Maps API"));
    document.head.appendChild(script);
  });
  return loadPromise;
}

export type { YMapInstance, YMapsApi };
