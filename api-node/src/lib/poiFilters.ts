/** Фильтры геокодера (parity с search/yandex/poi_filters.py). */

const TRANSPORT_NAME_RE =
  /(аэропорт|аэроп\.?|вокзал|станци[яи]\s|станция|причал|порт|ж\/д|жд|аэровокзал|автовокзал|перрон|аэро|метро|метрополитен|railway|airport|train\s+station)/i;

const GENERIC_AREA_RE =
  /(район\b|округ\b|область\b|микрорайон|садоводческ|товариществ)/i;

const SKIP_GEO_KINDS = new Set([
  "country",
  "region",
  "province",
  "area",
  "district",
  "locality",
]);

const SKIP_TRANSPORT_KINDS = new Set([
  "metro",
  "railway",
  "route",
  "station",
  "railway_station",
  "airport",
]);

const LEISURE_NAME_HINTS = [
  "муз",
  "галер",
  "театр",
  "парк",
  "филармон",
  "выстав",
  "достопримеч",
  "площад",
  "собор",
  "кремл",
  "заповедник",
  "мемориал",
  "памятн",
  "монумент",
  "стел",
  "усадьб",
  "дворец",
  "набереж",
  "сквер",
  "бульвар",
  "пешеходн",
  "покровск",
  "бауман",
  "променад",
  "монаст",
  "колокольн",
  "каланч",
  "ряды",
  "слобод",
  "дендропарк",
  "ресторан",
  "кафе",
  "столовая",
  "бистро",
  "кухня",
  "церков",
  "храм",
  "мечеть",
  "костел",
  "сад ",
  "сад,",
  "museum",
  "gallery",
  "park",
  "mosque",
  "palace",
  "church",
  "cathedral",
  "monument",
  "square",
  "basilica",
  "cistern",
  "bazaar",
  "tower",
  "fortress",
  "synagogue",
  "theatre",
  "theater",
  "camii",
  "cami",
  "kilise",
  "saray",
  "cami-i",
  "tomb",
  "fountain",
  "hamam",
];

const EMBANKMENT_STREET_RE =
  /(верхне|нижне)?-?набережная\s+улица|набережная\s+улица/i;
const STREET_PREFIX_RE =
  /^(улица|ул\.?|пер\.?|переулок|пр-т|проспект|шоссе|бульвар)\s+/i;
const HOUSE_SUFFIX_RE = /,\s*\d/i;

const CITY_ONLY = new Set([
  "кострома",
  "москва",
  "санкт-петербург",
  "спб",
  "казань",
  "сочи",
  "стамбул",
  "istanbul",
]);

function normalizeName(name: string): string {
  return name.toLowerCase().replace(/ё/g, "е").trim();
}

export function isTransportHub(name: string): boolean {
  return TRANSPORT_NAME_RE.test(normalizeName(name));
}

export function isGenericArea(name: string): boolean {
  return GENERIC_AREA_RE.test(normalizeName(name));
}

export function isGenericStreetName(name: string): boolean {
  const n = normalizeName(name);
  if (STREET_PREFIX_RE.test(n)) return true;
  if (EMBANKMENT_STREET_RE.test(n)) return true;
  if (HOUSE_SUFFIX_RE.test(n)) return true;
  if (n.endsWith(" улица") || n.endsWith(" ул")) return true;
  return false;
}

export function isCityOnlyName(name: string, cityHint = ""): boolean {
  const n = normalizeName(name);
  if (!n) return true;
  if (cityHint && n === normalizeName(cityHint)) return true;
  return CITY_ONLY.has(n);
}

export function looksLikeLeisurePoi(name: string): boolean {
  const lowered = normalizeName(name);
  return LEISURE_NAME_HINTS.some((hint) => lowered.includes(hint));
}

export function isAcceptablePlaceName(name: string, cityHint = ""): boolean {
  const cleaned = name.trim();
  if (!cleaned || cleaned.length < 3) return false;
  if (cityHint && normalizeName(cleaned) === normalizeName(cityHint)) {
    return false;
  }
  if (isTransportHub(cleaned)) return false;
  if (isGenericArea(cleaned)) return false;
  if (isGenericStreetName(cleaned)) return false;
  if (isCityOnlyName(cleaned, cityHint)) return false;
  return true;
}

export function isLandmarkPoiName(name: string, cityHint = ""): boolean {
  if (isCityOnlyName(name, cityHint)) return false;
  if (!isAcceptablePlaceName(name, cityHint)) return false;
  if (isGenericStreetName(name)) return false;
  return looksLikeLeisurePoi(name);
}

export interface YandexGeoMember {
  GeoObject?: {
    name?: string;
    Point?: { pos?: string };
    metaDataProperty?: {
      GeocoderMetaData?: {
        kind?: string;
        text?: string;
      };
    };
  };
}

export function isAcceptableGeoMember(
  member: YandexGeoMember,
  cityHint = "",
): boolean {
  const obj = member.GeoObject ?? {};
  const meta = obj.metaDataProperty?.GeocoderMetaData ?? {};
  const kind = String(meta.kind ?? "").toLowerCase();
  if (SKIP_GEO_KINDS.has(kind) || SKIP_TRANSPORT_KINDS.has(kind)) {
    return false;
  }
  const name = String(obj.name ?? "").trim();
  if (!isAcceptablePlaceName(name, cityHint)) return false;
  if (!String(obj.Point?.pos ?? "").trim()) return false;
  if (kind === "street") return isLandmarkPoiName(name, cityHint);
  if (kind === "vegetation" || kind === "hydro" || kind === "house" || kind === "other") {
    return isLandmarkPoiName(name, cityHint);
  }
  return isLandmarkPoiName(name, cityHint);
}
