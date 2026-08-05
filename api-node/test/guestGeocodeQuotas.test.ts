import { describe, expect, it } from "vitest";
import { GuestGeocodeQuotaError } from "../src/services/guestGeocodeQuotas.js";

describe("guest geocode quotas", () => {
  it("GuestGeocodeQuotaError carries limit metadata", () => {
    const err = new GuestGeocodeQuotaError("too many", 40, 3600);
    expect(err.message).toContain("too many");
    expect(err.limit).toBe(40);
    expect(err.windowSec).toBe(3600);
  });
});
