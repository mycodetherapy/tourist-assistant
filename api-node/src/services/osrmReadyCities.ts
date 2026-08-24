/** Каталог городов с готовым OSRM-графом на диске (для чипов на форме новой прогулки). */

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

export type OsrmReadyCity = {
  slug: string;
  display_name: string;
};

function resolveCitiesRoot(): string {
  const fromEnv = (process.env.TOURIST_DATA_DIR ?? "").trim();
  if (fromEnv) {
    return resolve(fromEnv, "cities");
  }
  // Локально: api-node cwd → ../data/cities; в Docker с volume: /app/data/cities
  const candidates = [
    resolve(process.cwd(), "../data/cities"),
    resolve(process.cwd(), "data/cities"),
    resolve(process.cwd(), "../../data/cities"),
    "/app/data/cities",
  ];
  for (const path of candidates) {
    if (existsSync(path)) return path;
  }
  return candidates[0]!;
}

function resolveCityPacksYaml(): string | null {
  const fromEnv = (process.env.CITY_PACKS_YAML ?? "").trim();
  if (fromEnv && existsSync(fromEnv)) return fromEnv;
  const candidates = [
    resolve(process.cwd(), "../config/city_packs.yaml"),
    resolve(process.cwd(), "config/city_packs.yaml"),
    resolve(process.cwd(), "../../config/city_packs.yaml"),
    "/app/config/city_packs.yaml",
  ];
  for (const path of candidates) {
    if (existsSync(path)) return path;
  }
  return null;
}

/** Минимальный разбор default_packs: slug + display_name. */
export function parseCityPackDisplayNames(yamlText: string): Map<string, string> {
  const out = new Map<string, string>();
  let slug: string | null = null;
  for (const raw of yamlText.split(/\r?\n/)) {
    const slugMatch = raw.match(/^\s+-\s+slug:\s*(.+?)\s*$/);
    if (slugMatch) {
      slug = slugMatch[1]!.replace(/^["']|["']$/g, "").trim();
      continue;
    }
    const nameMatch = raw.match(/^\s+display_name:\s*(.+?)\s*$/);
    if (nameMatch && slug) {
      const name = nameMatch[1]!.replace(/^["']|["']$/g, "").trim();
      if (name) out.set(slug, name);
      slug = null;
    }
  }
  return out;
}

function isOsrmGraphReady(citiesRoot: string, slug: string): boolean {
  return existsSync(join(citiesRoot, slug, "osrm", `${slug}.osrm.mldgr`));
}

export function listOsrmReadyCities(): OsrmReadyCity[] {
  const citiesRoot = resolveCitiesRoot();
  if (!existsSync(citiesRoot)) {
    return [];
  }

  let names = new Map<string, string>();
  const yamlPath = resolveCityPacksYaml();
  if (yamlPath) {
    try {
      names = parseCityPackDisplayNames(readFileSync(yamlPath, "utf8"));
    } catch {
      names = new Map();
    }
  }

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
