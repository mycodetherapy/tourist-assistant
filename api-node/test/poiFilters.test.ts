import { describe, expect, it } from "vitest";
import {
  isAcceptableGeoMember,
  isAcceptablePlaceName,
  isGenericStreetName,
  isLandmarkPoiName,
  isTransportHub,
} from "../src/lib/poiFilters.js";

describe("poiFilters", () => {
  it("rejects transport hubs", () => {
    expect(isTransportHub("станция Кострома")).toBe(true);
    expect(isAcceptablePlaceName("станция Кострома")).toBe(false);
    expect(isAcceptablePlaceName("метро Площадь Революции")).toBe(false);
  });

  it("accepts landmarks", () => {
    expect(isAcceptablePlaceName("Сусанинская площадь")).toBe(true);
    expect(isLandmarkPoiName("Сусанинская площадь")).toBe(true);
  });

  it("rejects generic streets", () => {
    expect(isGenericStreetName("улица Красные Ряды")).toBe(true);
    expect(isLandmarkPoiName("улица Красные Ряды")).toBe(false);
    expect(isLandmarkPoiName("Волжская набережная", "Самара")).toBe(true);
  });

  it("accepts named embankment geo member", () => {
    const member = {
      GeoObject: {
        name: "Волжская набережная",
        Point: { pos: "50.15 53.20" },
        metaDataProperty: {
          GeocoderMetaData: {
            kind: "street",
            text: "Россия, Самарская область, Самара, Волжская набережная",
          },
        },
      },
    };
    expect(isAcceptableGeoMember(member, "Самара")).toBe(true);
  });
});
