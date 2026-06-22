import "./setup-env.js";

import { describe, expect, it } from "vitest";

describe("googleOAuth state", () => {
  it("signs and verifies state", async () => {
    process.env.GOOGLE_CLIENT_ID = "test-client-id";
    process.env.GOOGLE_CLIENT_SECRET = "test-client-secret";
    const { buildGoogleAuthorizeUrl, verifyOAuthState } = await import(
      "../src/services/googleOAuth.js"
    );
    const { state } = buildGoogleAuthorizeUrl("http://localhost:5173");
    expect(verifyOAuthState(state)).toBe(true);
    expect(verifyOAuthState("bad")).toBe(false);
  });
});
