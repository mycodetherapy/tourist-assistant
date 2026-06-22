import { describe, expect, it, vi, afterEach } from "vitest";

describe("geocodePlaces", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.YANDEX_MAPS_API_KEY;
  });

  it("falls back to Nominatim when Yandex key is missing", async () => {
    process.env.YANDEX_MAPS_API_KEY = "";
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("nominatim.openstreetmap.org")) {
        return {
          ok: true,
          json: async () => [
            {
              lat: "43.5855",
              lon: "39.7231",
              display_name: "Sochi, Russia",
            },
          ],
        };
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { geocodePlaces } = await import("../src/services/geocode.js");
    const results = await geocodePlaces("Сочи", "Сочи");
    expect(results).toHaveLength(1);
    expect(results[0]!.lat).toBeCloseTo(43.5855, 2);
    expect(results[0]!.lon).toBeCloseTo(39.7231, 2);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("nominatim.openstreetmap.org"),
      expect.any(Object),
    );
  });

  it("filters transport hubs from Yandex results", async () => {
    process.env.YANDEX_MAPS_API_KEY = "test-key";
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("geocode-maps.yandex")) {
        return {
          ok: true,
          json: async () => ({
            response: {
              GeoObjectCollection: {
                featureMember: [
                  {
                    GeoObject: {
                      name: "станция Кострома",
                      Point: { pos: "41.0 57.0" },
                      metaDataProperty: {
                        GeocoderMetaData: {
                          kind: "railway_station",
                          text: "станция",
                        },
                      },
                    },
                  },
                ],
              },
            },
          }),
        };
      }
      if (url.includes("nominatim")) {
        return { ok: true, json: async () => [] };
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { geocodePlaces } = await import("../src/services/geocode.js");
    const results = await geocodePlaces("Кострома", "Кострома");
    expect(results).toHaveLength(0);
  });
});
