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
