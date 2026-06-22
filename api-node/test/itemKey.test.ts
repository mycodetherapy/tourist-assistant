import { describe, expect, it } from "vitest";
import { makeItemKey, makeRouteStopKey, parseRouteStopKey } from "../src/lib/itemKey.js";

describe("itemKey", () => {
  it("matches Python make_item_key", () => {
    const text = "  Вариант  A  \n  с  текстом  ";
    expect(makeItemKey("routes", text)).toBe(
      makeItemKey("routes", "вариант a с текстом"),
    );
    expect(makeItemKey("routes", "Hello")).toHaveLength(16);
  });

  it("route stop keys", () => {
    expect(makeRouteStopKey("wd:Q123")).toBe("poi:wd:Q123");
    expect(parseRouteStopKey("poi:wd:Q123")).toBe("wd:Q123");
  });
});
