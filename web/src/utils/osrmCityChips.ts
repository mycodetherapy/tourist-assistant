import type { OsrmReadyCity } from "../api/cities";

export const OSRM_RECENT_CITIES_KEY = "osrm-ready-city-recent";
export const OSRM_RECENT_CITIES_MAX = 5;

export function normalizeCityQuery(raw: string): string {
  return (raw || "")
    .trim()
    .toLowerCase()
    .replace(/ё/g, "е")
    .replace(/[-–—]/g, " ")
    .replace(/\s+/g, " ");
}

export function cityMatchesQuery(city: OsrmReadyCity, query: string): boolean {
  const q = normalizeCityQuery(query);
  if (!q) {
    return true;
  }
  const name = normalizeCityQuery(city.display_name);
  const slug = normalizeCityQuery(city.slug);
  return name.includes(q) || slug.includes(q);
}

export function findExactOsrmCity(
  cities: OsrmReadyCity[],
  query: string,
): OsrmReadyCity | undefined {
  const q = normalizeCityQuery(query);
  if (!q) {
    return undefined;
  }
  return cities.find((city) => normalizeCityQuery(city.display_name) === q);
}

export function readRecentOsrmSlugs(): string[] {
  try {
    const raw = localStorage.getItem(OSRM_RECENT_CITIES_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item): item is string => typeof item === "string" && item.length > 0);
  } catch {
    return [];
  }
}

export function rememberRecentOsrmSlug(slug: string): void {
  const id = slug.trim();
  if (!id) {
    return;
  }
  const next = [id, ...readRecentOsrmSlugs().filter((item) => item !== id)].slice(
    0,
    OSRM_RECENT_CITIES_MAX,
  );
  try {
    localStorage.setItem(OSRM_RECENT_CITIES_KEY, JSON.stringify(next));
  } catch {
    /* private mode / quota */
  }
}

export function sortOsrmCities(
  cities: OsrmReadyCity[],
  recentSlugs: string[],
  selectedQuery: string,
): OsrmReadyCity[] {
  const exact = findExactOsrmCity(cities, selectedQuery);
  return [...cities].sort((a, b) => {
    if (exact) {
      if (a.slug === exact.slug) return -1;
      if (b.slug === exact.slug) return 1;
    }
    const aRecent = recentSlugs.indexOf(a.slug);
    const bRecent = recentSlugs.indexOf(b.slug);
    const aRank = aRecent === -1 ? 999 : aRecent;
    const bRank = bRecent === -1 ? 999 : bRecent;
    if (aRank !== bRank) {
      return aRank - bRank;
    }
    return a.display_name.localeCompare(b.display_name, "ru", { sensitivity: "base" });
  });
}

export function visibleOsrmCities(
  cities: OsrmReadyCity[],
  query: string,
  expanded: boolean,
  collapsedLimit: number,
): { shown: OsrmReadyCity[]; hidden: number; filtering: boolean } {
  const filtering = normalizeCityQuery(query).length > 0;
  const matched = filtering
    ? cities.filter((city) => cityMatchesQuery(city, query))
    : cities;
  if (filtering || expanded || matched.length <= collapsedLimit) {
    return { shown: matched, hidden: 0, filtering };
  }
  return {
    shown: matched.slice(0, collapsedLimit),
    hidden: matched.length - collapsedLimit,
    filtering,
  };
}
