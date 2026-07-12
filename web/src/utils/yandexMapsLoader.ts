type YMapGeoObjectCollection = {
  add: (obj: unknown) => void;
  remove: (obj: unknown) => void;
};

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
  geoObjects: YMapGeoObjectCollection;
  setCenter: (center: number[], zoom?: number) => void;
  setBounds: (bounds: number[][], options?: Record<string, unknown>) => void;
  setZoom: (zoom: number) => void;
  getZoom: () => number;
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

const YMAPS_READY_TIMEOUT_MS = 25_000;

function withTimeout<T>(promise: Promise<T>, ms: number, message: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error(message)), ms);
    promise
      .then((value) => {
        window.clearTimeout(timer);
        resolve(value);
      })
      .catch((error: unknown) => {
        window.clearTimeout(timer);
        reject(error);
      });
  });
}

function ymapsReady(ymaps: YMapsApi): Promise<YMapsApi> {
  return new Promise((resolve, reject) => {
    try {
      ymaps.ready(() => resolve(ymaps));
    } catch (error: unknown) {
      reject(error instanceof Error ? error : new Error(String(error)));
    }
  });
}

function injectYandexMapsScript(apiKey: string): Promise<YMapsApi> {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `https://api-maps.yandex.ru/2.1/?apikey=${encodeURIComponent(apiKey)}&lang=ru_RU`;
    script.async = true;
    script.onload = () => {
      if (!window.ymaps) {
        reject(new Error("Yandex Maps API не загрузился"));
        return;
      }
      void withTimeout(
        ymapsReady(window.ymaps),
        YMAPS_READY_TIMEOUT_MS,
        "Yandex Maps API не ответил вовремя (проверьте ключ и домен в кабинете Яндекса)",
      )
        .then(resolve)
        .catch(reject);
    };
    script.onerror = () => reject(new Error("Не удалось загрузить Yandex Maps API"));
    document.head.appendChild(script);
  });
}

export function getYandexMapsApiKey(): string {
  return (import.meta.env.VITE_YANDEX_MAPS_API_KEY as string | undefined)?.trim() ?? "";
}

export function isYandexMapsConfigured(): boolean {
  return getYandexMapsApiKey().length > 0;
}

export function loadYandexMaps(): Promise<YMapsApi> {
  if (loadPromise) {
    return loadPromise;
  }

  const apiKey = getYandexMapsApiKey();
  if (!apiKey) {
    return Promise.reject(new Error("VITE_YANDEX_MAPS_API_KEY не задан"));
  }

  if (window.ymaps) {
    loadPromise = withTimeout(
      ymapsReady(window.ymaps),
      YMAPS_READY_TIMEOUT_MS,
      "Yandex Maps API не ответил вовремя",
    ).catch((error) => {
      loadPromise = null;
      throw error;
    });
    return loadPromise;
  }

  loadPromise = injectYandexMapsScript(apiKey).catch((error) => {
    loadPromise = null;
    throw error;
  });
  return loadPromise;
}

export type { YMapInstance, YMapsApi };
