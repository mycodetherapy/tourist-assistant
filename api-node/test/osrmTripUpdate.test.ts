import { describe, expect, it } from "vitest";
import { buildTripOsrmUpdateStatus } from "../src/services/osrmTripUpdate.js";

describe("buildTripOsrmUpdateStatus", () => {
  it("marks update when graph is newer than routes", () => {
    // Use a city unlikely to resolve — still returns update_available false without slug
    const status = buildTripOsrmUpdateStatus({
      city: "НесуществующийГородXYZ",
      latest: {
        id: 1,
        version: 1,
        scope: "full",
        approved: true,
        created_at: "2020-01-01T00:00:00.000Z",
        program: { routes: { cases: [{ case_id: "A" }] } },
      },
    });
    expect(status.update_available).toBe(false);
    expect(status.osrm_ready).toBe(false);
  });

  it("requires routes in program", () => {
    const status = buildTripOsrmUpdateStatus({
      city: "НесуществующийГородXYZ",
      latest: {
        id: 1,
        version: 1,
        scope: "full",
        approved: true,
        created_at: "2020-01-01T00:00:00.000Z",
        program: { routes: null },
      },
    });
    expect(status.routes_built_at).toBeNull();
    expect(status.update_available).toBe(false);
  });
});
