/** Каталог: OSRM ready / eligible (FO на диске, графа ещё нет). */

import { existsSync, readdirSync, readFileSync, statfsSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

export type OsrmReadyCity = {
  slug: string;
  display_name: string;
};

export type OsrmEligibleCity = OsrmReadyCity & {
  federal_district: string;
};

export type CityPackEntry = {
  slug: string;
  display_name: string;
  federal_district: string;
  names: string[];
};

function resolveDataRoot(): string {
  const fromEnv = (process.env.TOURIST_DATA_DIR ?? "").trim();
  if (fromEnv) return resolve(fromEnv);
  const candidates = [
    resolve(process.cwd(), "../data"),
    resolve(process.cwd(), "data"),
    resolve(process.cwd(), "../../data"),
    "/app/data",
  ];
  for (const path of candidates) {
    if (existsSync(path)) return path;
  }
  return candidates[0]!;
}

export function resolveCitiesRoot(): string {
  return join(resolveDataRoot(), "cities");
}

export function resolveFoRoot(): string {
  return join(resolveDataRoot(), "fo");
}

function resolveConfigFile(name: string): string | null {
  const candidates = [
    resolve(process.cwd(), `../config/${name}`),
    resolve(process.cwd(), `config/${name}`),
    resolve(process.cwd(), `../../config/${name}`),
    `/app/config/${name}`,
  ];
  for (const path of candidates) {
    if (existsSync(path)) return path;
  }
  return null;
}

/** Минимальный разбор default_packs: slug + display_name. */
export function parseCityPackDisplayNames(yamlText: string): Map<string, string> {
  const out = new Map<string, string>();
  for (const entry of parseCityPackEntries(yamlText)) {
    out.set(entry.slug, entry.display_name);
  }
  return out;
}

export function parseCityPackEntries(yamlText: string): CityPackEntry[] {
  const out: CityPackEntry[] = [];
  let slug: string | null = null;
  let displayName: string | null = null;
  let federalDistrict: string | null = null;
  let names: string[] = [];

  const flush = () => {
    if (slug && displayName && federalDistrict) {
      const aliases = names.length ? names : [displayName, slug];
      out.push({
        slug,
        display_name: displayName,
        federal_district: federalDistrict,
        names: aliases,
      });
    }
    slug = null;
    displayName = null;
    federalDistrict = null;
    names = [];
  };

  for (const raw of yamlText.split(/\r?\n/)) {
    const slugMatch = raw.match(/^\s+-\s+slug:\s*(.+?)\s*$/);
    if (slugMatch) {
      flush();
      slug = slugMatch[1]!.replace(/^["']|["']$/g, "").trim();
      continue;
    }
    const nameMatch = raw.match(/^\s+display_name:\s*(.+?)\s*$/);
    if (nameMatch && slug) {
      displayName = nameMatch[1]!.replace(/^["']|["']$/g, "").trim();
      continue;
    }
    const foMatch = raw.match(/^\s+federal_district:\s*(.+?)\s*$/);
    if (foMatch && slug) {
      federalDistrict = foMatch[1]!.replace(/^["']|["']$/g, "").trim();
      continue;
    }
    const namesMatch = raw.match(/^\s+names:\s*\[(.*)\]\s*$/);
    if (namesMatch && slug) {
      names = namesMatch[1]!
        .split(",")
        .map((s) => s.replace(/^["'\s]+|["'\s]+$/g, "").trim())
        .filter(Boolean);
    }
  }
  flush();
  return out;
}

type FoMeta = { pbf_name: string; min_pbf_bytes: number };

export function parseFederalDistricts(yamlText: string): Map<string, FoMeta> {
  const out = new Map<string, FoMeta>();
  let foId: string | null = null;
  let pbfName: string | null = null;
  let minBytes = 50 * 1024 * 1024;

  const flush = () => {
    if (foId && pbfName) {
      out.set(foId, { pbf_name: pbfName, min_pbf_bytes: minBytes });
    }
    foId = null;
    pbfName = null;
    minBytes = 50 * 1024 * 1024;
  };

  let inDistricts = false;
  for (const raw of yamlText.split(/\r?\n/)) {
    if (/^districts:\s*$/.test(raw)) {
      inDistricts = true;
      continue;
    }
    if (!inDistricts) continue;
    const idMatch = raw.match(/^  ([a-z0-9_-]+):\s*$/);
    if (idMatch) {
      flush();
      foId = idMatch[1]!;
      continue;
    }
    const pbfMatch = raw.match(/^\s+pbf_name:\s*(.+?)\s*$/);
    if (pbfMatch && foId) {
      pbfName = pbfMatch[1]!.replace(/^["']|["']$/g, "").trim();
      continue;
    }
    const minMatch = raw.match(/^\s+min_pbf_bytes:\s*(\d+)\s*$/);
    if (minMatch && foId) {
      minBytes = Number(minMatch[1]);
    }
  }
  flush();
  return out;
}

export function isOsrmGraphReady(citiesRoot: string, slug: string): boolean {
  return existsSync(join(citiesRoot, slug, "osrm", `${slug}.osrm.mldgr`));
}

export function isFoReadyOnDisk(foRoot: string, meta: FoMeta): boolean {
  const path = join(foRoot, meta.pbf_name);
  if (!existsSync(path)) return false;
  try {
    return statSync(path).size >= meta.min_pbf_bytes;
  } catch {
    return false;
  }
}

function loadPackEntries(): CityPackEntry[] {
  const yamlPath = resolveConfigFile("city_packs.yaml");
  if (!yamlPath) return [];
  try {
    return parseCityPackEntries(readFileSync(yamlPath, "utf8"));
  } catch {
    return [];
  }
}

function loadFoMap(): Map<string, FoMeta> {
  const yamlPath = resolveConfigFile("federal_districts.yaml");
  if (!yamlPath) return new Map();
  try {
    return parseFederalDistricts(readFileSync(yamlPath, "utf8"));
  } catch {
    return new Map();
  }
}

export function listOsrmReadyCities(): OsrmReadyCity[] {
  const citiesRoot = resolveCitiesRoot();
  if (!existsSync(citiesRoot)) {
    return [];
  }
  const names = new Map(
    loadPackEntries().map((e) => [e.slug, e.display_name] as const),
  );
  const slugs = readdirSync(citiesRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .filter((slug) => isOsrmGraphReady(citiesRoot, slug));

  return slugs
    .map((slug) => ({
      slug,
      display_name: names.get(slug) ?? slug,
    }))
    .sort((a, b) =>
      a.display_name.localeCompare(b.display_name, "ru", { sensitivity: "base" }),
    );
}

export function countOsrmReadyCities(): number {
  return listOsrmReadyCities().length;
}

/** Города каталога: FO на диске есть, OSRM-графа ещё нет. */
export function listOsrmEligibleCities(): OsrmEligibleCity[] {
  const citiesRoot = resolveCitiesRoot();
  const foRoot = resolveFoRoot();
  const foMap = loadFoMap();
  const entries = loadPackEntries();

  return entries
    .filter((entry) => {
      const fo = foMap.get(entry.federal_district);
      if (!fo || !isFoReadyOnDisk(foRoot, fo)) return false;
      return !isOsrmGraphReady(citiesRoot, entry.slug);
    })
    .map((entry) => ({
      slug: entry.slug,
      display_name: entry.display_name,
      federal_district: entry.federal_district,
    }))
    .sort((a, b) =>
      a.display_name.localeCompare(b.display_name, "ru", { sensitivity: "base" }),
    );
}

export function getCityPackEntry(slug: string): CityPackEntry | null {
  return loadPackEntries().find((e) => e.slug === slug) ?? null;
}

function normalizeCityKey(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/ё/g, "е")
    .replace(/[^a-z0-9а-я]+/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Resolve trip.city → catalog slug (names / display_name / slug). */
export function resolveCitySlug(city: string): string | null {
  const key = normalizeCityKey(city);
  if (!key) return null;
  for (const entry of loadPackEntries()) {
    if (normalizeCityKey(entry.slug) === key) return entry.slug;
    if (normalizeCityKey(entry.display_name) === key) return entry.slug;
    for (const name of entry.names) {
      if (normalizeCityKey(name) === key) return entry.slug;
    }
  }
  return null;
}

/** mtime ISO of <slug>.osrm.mldgr, or null if missing. */
export function getOsrmGraphUpdatedAt(slug: string): string | null {
  const path = join(resolveCitiesRoot(), slug, "osrm", `${slug}.osrm.mldgr`);
  if (!existsSync(path)) return null;
  try {
    return statSync(path).mtime.toISOString();
  } catch {
    return null;
  }
}

export function getFreeDiskBytes(dataRoot?: string): number | null {
  const root = dataRoot || resolveDataRoot();
  try {
    const st = statfsSync(root);
    return Number(st.bavail) * Number(st.bsize);
  } catch {
    return null;
  }
}

export function assertDiskHasFreeGb(minGb: number): void {
  const free = getFreeDiskBytes();
  if (free == null) return;
  const minBytes = minGb * 1024 * 1024 * 1024;
  if (free < minBytes) {
    throw new Error(
      `Недостаточно места на диске (нужно ≥${minGb} ГБ свободно)`,
    );
  }
}
