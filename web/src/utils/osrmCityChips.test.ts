import { describe, expect, it } from "vitest";
import type { OsrmReadyCity } from "../api/cities";
import {
  cityMatchesQuery,
  findExactOsrmCity,
  normalizeCityQuery,
  sortOsrmCities,
  visibleOsrmCities,
} from "./osrmCityChips";

const cities: OsrmReadyCity[] = [
  { slug: "kazan", display_name: "Казань" },
  { slug: "yoshkar-ola", display_name: "Йошкар-Ола" },
  { slug: "moscow", display_name: "Москва" },
  { slug: "spb", display_name: "Санкт-Петербург" },
];

describe("osrm city chips helpers", () => {
  it("normalizes yo and dashes", () => {
    expect(normalizeCityQuery("  Йошкар-Ола ")).toBe("йошкар ола");
  });

  it("matches display name and slug", () => {
    expect(cityMatchesQuery(cities[1]!, "йошкар")).toBe(true);
    expect(cityMatchesQuery(cities[0]!, "kazan")).toBe(true);
    expect(cityMatchesQuery(cities[0]!, "петербург")).toBe(false);
  });

  it("finds exact city ignoring yo", () => {
    expect(findExactOsrmCity(cities, "казань")?.slug).toBe("kazan");
    expect(findExactOsrmCity(cities, "Каза")).toBeUndefined();
  });

  it("pins exact and recent before alphabet", () => {
    const sorted = sortOsrmCities(cities, ["spb"], "Казань");
    expect(sorted.map((c) => c.slug)).toEqual([
      "kazan",
      "spb",
      "moscow",
      "yoshkar-ola",
    ]);
  });

  it("collapses when idle and expands when filtering", () => {
    const idle = visibleOsrmCities(cities, "", false, 2);
    expect(idle.shown).toHaveLength(2);
    expect(idle.hidden).toBe(2);

    const typed = visibleOsrmCities(cities, "ск", false, 2);
    expect(typed.filtering).toBe(true);
    expect(typed.hidden).toBe(0);
    expect(typed.shown.map((c) => c.slug)).toContain("moscow");
  });
});
