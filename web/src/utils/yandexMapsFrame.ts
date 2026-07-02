/** URL маршрута в формате from=mapframe (как кнопка в iframe-виджете Яндекса). */

import { parseMapsRoutePoints } from "./mapsRoutePoints";

const CITY_YANDEX_PATH: Record<string, string> = {
  казань: "43/kazan",
  kazan: "43/kazan",
  "йошкар-ола": "48/yoshkar-ola",
  "yoshkar-ola": "48/yoshkar-ola",
  кострома: "7/kostroma",
  kostroma: "7/kostroma",
  москва: "213/moscow",
  moscow: "213/moscow",
  "санкт-петербург": "2/saint-petersburg",
  "saint-petersburg": "2/saint-petersburg",
  "нижний новгород": "47/nizhny-novgorod",
  "nizhny novgorod": "47/nizhny-novgorod",
  "nizhny-novgorod": "47/nizhny-novgorod",
  ульяновск: "195/ulyanovsk",
  ulyanovsk: "195/ulyanovsk",
  самара: "51/samara",
  samara: "51/samara",
  тольятти: "240/tolyatti",
  tolyatti: "240/tolyatti",
  ижевск: "44/izhevsk",
  izhevsk: "44/izhevsk",
};

export function cityYandexMapsPath(city: string): string {
  const key = city.trim().toLowerCase().replace(/ё/g, "е");
  return CITY_YANDEX_PATH[key] ?? "";
}

function ruriForPointCount(pointCount: number): string {
  return "~".repeat(Math.max(0, pointCount - 1));
}

function routeCenter(points: { lat: number; lon: number }[]): { lat: number; lon: number } {
  if (points.length === 0) {
    return { lat: 0, lon: 0 };
  }
  const lat = points.reduce((sum, p) => sum + p.lat, 0) / points.length;
  const lon = points.reduce((sum, p) => sum + p.lon, 0) / points.length;
  return { lat, lon };
}

export function buildMapsFrameRouteUrl(
  rtext: string,
  llLon: number,
  llLat: number,
  city = "",
  z = "15",
): string {
  const parts = rtext.split("~").map((chunk) => chunk.trim()).filter(Boolean);
  const params = new URLSearchParams();
  params.set("from", "mapframe");
  params.set("source", "mapframe");
  params.set("utm_source", "mapframe");
  params.set("ll", `${llLon},${llLat}`);
  params.set("mode", "routes");
  params.set("rtext", rtext);
  params.set("rtt", "pd");
  params.set("ruri", ruriForPointCount(parts.length));
  params.set("z", z);

  const path = cityYandexMapsPath(city);
  const base = path ? `https://yandex.ru/maps/${path}/` : "https://yandex.ru/maps/";
  return `${base}?${params.toString()}`;
}

/** Прямая ссылка на маршрут в Яндекс.Картах (без модалки и без map-widget). */
export function mapsUrlToFrameRouteUrl(mapsRouteUrl: string, city = ""): string | null {
  const trimmed = mapsRouteUrl.trim();
  if (!trimmed) {
    return null;
  }
  try {
    const source = new URL(trimmed);
    if (!source.hostname.includes("yandex.")) {
      return null;
    }
    const rtext = source.searchParams.get("rtext");
    if (!rtext) {
      return null;
    }
    const llRaw = source.searchParams.get("ll");
    let llLon: number;
    let llLat: number;
    if (llRaw?.includes(",")) {
      const [lonS, latS] = llRaw.split(",", 2);
      llLon = Number.parseFloat(lonS);
      llLat = Number.parseFloat(latS);
    } else {
      const center = routeCenter(parseMapsRoutePoints(trimmed));
      llLon = center.lon;
      llLat = center.lat;
    }
    if (!Number.isFinite(llLon) || !Number.isFinite(llLat)) {
      return null;
    }
    const z = source.searchParams.get("z") ?? "15";
    return buildMapsFrameRouteUrl(rtext, llLon, llLat, city, z);
  } catch {
    return null;
  }
}
