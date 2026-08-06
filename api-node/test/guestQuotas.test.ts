import { describe, expect, it } from "vitest";
import {
  assertGuestCanCreateTrip,
  assertGuestCanStartRun,
  GuestRegisterRequiredError,
  GUEST_FULL_RUN_LIMIT,
  GUEST_PARTIAL_RUN_LIMIT,
} from "../src/services/guestQuotas.js";
import type { GuestSessionRow } from "../src/repos/guestSessions.js";

function session(overrides: Partial<GuestSessionRow> = {}): GuestSessionRow {
  return {
    id: "00000000-0000-4000-8000-000000000001",
    user_id: 1,
    trip_id: null,
    full_runs_used: 0,
    partial_runs_used: 0,
    expires_at: new Date(Date.now() + 86400000).toISOString(),
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("guest quotas", () => {
  it("allows first full build on empty session", () => {
    expect(() => assertGuestCanCreateTrip(session())).not.toThrow();
    expect(() => assertGuestCanStartRun(session(), "full")).not.toThrow();
  });

  it("blocks second trip", () => {
    expect(() => assertGuestCanCreateTrip(session({ trip_id: 42 }))).toThrow(
      GuestRegisterRequiredError,
    );
  });

  it("blocks full run after limit", () => {
    expect(() =>
      assertGuestCanStartRun(session({ full_runs_used: GUEST_FULL_RUN_LIMIT }), "full"),
    ).toThrow(GuestRegisterRequiredError);
  });

  it("allows one partial rebuild", () => {
    expect(() => assertGuestCanStartRun(session(), "routes")).not.toThrow();
    expect(() =>
      assertGuestCanStartRun(
        session({ partial_runs_used: GUEST_PARTIAL_RUN_LIMIT }),
        "routes",
      ),
    ).toThrow(GuestRegisterRequiredError);
  });
});
