import { describe, expect, it } from "vitest";
import { getOsrmPrepareLock } from "../src/services/osrmPrepareAccess.js";

describe("getOsrmPrepareLock", () => {
  it("blocks free mode even if a key is stored", () => {
    const lock = getOsrmPrepareLock("none", true);
    expect(lock?.code).toBe("free_mode");
    expect(lock?.message).toMatch(/бесплатн/i);
  });

  it("blocks BYOK without a saved key", () => {
    const lock = getOsrmPrepareLock("byok", false);
    expect(lock?.code).toBe("need_key");
  });

  it("allows BYOK with a saved key", () => {
    expect(getOsrmPrepareLock("byok", true)).toBeNull();
  });

  it("blocks platform mode", () => {
    expect(getOsrmPrepareLock("platform", true)?.code).toBe("platform");
  });
});
