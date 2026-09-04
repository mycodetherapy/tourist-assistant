import { describe, expect, it } from "vitest";
import {
  hashAuthSessionToken,
  newAuthSessionToken,
} from "../src/repos/authSessions.js";

describe("auth session token", () => {
  it("hashes stably and tokens differ", () => {
    const a = newAuthSessionToken();
    const b = newAuthSessionToken();
    expect(a).not.toBe(b);
    expect(hashAuthSessionToken(a)).toBe(hashAuthSessionToken(a));
    expect(hashAuthSessionToken(a)).not.toBe(hashAuthSessionToken(b));
    expect(hashAuthSessionToken(a)).toMatch(/^[a-f0-9]{64}$/);
  });
});
