import { describe, expect, it } from "vitest";
import { osrmPrepareQuotaUnlimited } from "../src/services/osrmPrepareAccess.js";

describe("osrmPrepareQuotaUnlimited", () => {
  it("applies quota in free mode even if a key is stored", () => {
    expect(osrmPrepareQuotaUnlimited("none", true)).toBe(false);
  });

  it("applies quota for BYOK without a saved key", () => {
    expect(osrmPrepareQuotaUnlimited("byok", false)).toBe(false);
  });

  it("lifts quota for BYOK with a saved key", () => {
    expect(osrmPrepareQuotaUnlimited("byok", true)).toBe(true);
  });

  it("keeps quota in platform mode", () => {
    expect(osrmPrepareQuotaUnlimited("platform", true)).toBe(false);
  });
});
