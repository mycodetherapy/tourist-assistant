import { existsSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  listOsrmReadyCities,
  parseCityPackDisplayNames,
} from "../src/services/osrmReadyCities.js";

describe("parseCityPackDisplayNames", () => {
  it("parses slug and display_name pairs", () => {
    const yaml = `
default_packs:
  - slug: moscow
    tier: hot
    display_name: Москва
    federal_district: central
  - slug: tbilisi
    display_name: Тбилиси
    federal_district: georgia
`;
    const map = parseCityPackDisplayNames(yaml);
    expect(map.get("moscow")).toBe("Москва");
    expect(map.get("tbilisi")).toBe("Тбилиси");
  });
});

describe("parseCityPackEntries + federal districts", () => {
  it("parses federal_district and FO meta", async () => {
    const { parseCityPackEntries, parseFederalDistricts } = await import(
      "../src/services/osrmReadyCities.js"
    );
    const entries = parseCityPackEntries(`
default_packs:
  - slug: moscow
    display_name: Москва
    federal_district: central
`);
    expect(entries[0]).toMatchObject({
      slug: "moscow",
      federal_district: "central",
    });
    const fo = parseFederalDistricts(`
districts:
  central:
    pbf_name: central-fed-district-latest.osm.pbf
    geofabrik_url: https://example.com/x.osm.pbf
    min_pbf_bytes: 1000
`);
    expect(fo.get("central")?.pbf_name).toBe("central-fed-district-latest.osm.pbf");
  });
});

describe("listOsrmReadyCities", () => {
  it("returns cities with mldgr when local data exists", () => {
    const cities = listOsrmReadyCities();
    expect(Array.isArray(cities)).toBe(true);
    for (const city of cities) {
      expect(city.slug).toBeTruthy();
      expect(city.display_name).toBeTruthy();
    }
    if (existsSync("../data/cities/kazan/osrm/kazan.osrm.mldgr")) {
      const kazan = cities.find((c) => c.slug === "kazan");
      expect(kazan?.display_name).toMatch(/казань/i);
    }
  });
});
