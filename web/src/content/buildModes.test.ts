import { describe, expect, it } from "vitest";
import {
  parsePoolCount,
  parsePoolProvider,
  providerLabel,
} from "./buildModes";

describe("buildModes pool parsing", () => {
  it("parses osm and wikidata summaries", () => {
    expect(parsePoolProvider("Пул: 89 мест досуга (osm). Варианты")).toBe("osm");
    expect(parsePoolProvider("Пул: 50 мест досуга (wikidata).")).toBe("wikidata");
    expect(parsePoolCount("Пул: 45 мест досуга (osm).")).toBe(45);
    expect(providerLabel("osm")).toContain("справочник");
    expect(providerLabel("wikidata")).toBe("Wikipedia");
  });
});
