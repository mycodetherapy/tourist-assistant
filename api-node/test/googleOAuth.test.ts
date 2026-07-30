import "./setup-env.js";

import { describe, expect, it } from "vitest";

describe("googleOAuth state", () => {
  it("signs and verifies state", async () => {
    process.env.GOOGLE_CLIENT_ID = "test-client-id";
    process.env.GOOGLE_CLIENT_SECRET = "test-client-secret";
    process.env.FRONTEND_URL = "https://localhost:5173";
    process.env.CORS_ORIGINS = "";
    const { buildGoogleAuthorizeUrl, verifyOAuthState, isAllowedFrontendOrigin } =
      await import("../src/services/googleOAuth.js");

    const httpLocal = buildGoogleAuthorizeUrl("http://localhost:5173");
    expect(httpLocal.redirectUri).toBe(
      "https://localhost:5173/api/auth/google/callback",
    );

    const https = buildGoogleAuthorizeUrl("https://localhost:5173");
    expect(https.redirectUri).toBe(
      "https://localhost:5173/api/auth/google/callback",
    );
    expect(verifyOAuthState(https.state)).toBe(true);
    expect(verifyOAuthState("bad")).toBe(false);
    expect(https.url).toContain(encodeURIComponent(https.redirectUri));

    const loopback = buildGoogleAuthorizeUrl("https://127.0.0.1:5173");
    expect(loopback.redirectUri).toBe(
      "https://localhost:5173/api/auth/google/callback",
    );

    const lan = buildGoogleAuthorizeUrl("https://192.168.1.81:5173");
    expect(lan.redirectUri).toBe(
      "https://192.168.1.81:5173/api/auth/google/callback",
    );

    process.env.FRONTEND_URL = "https://progulyai.ru";
    process.env.CORS_ORIGINS = "https://progulyai.ru";
    const { buildGoogleAuthorizeUrl: buildProd } = await import(
      "../src/services/googleOAuth.js"
    );
    const prod = buildProd("https://progulyai.ru");
    expect(prod.redirectUri).toBe(
      "https://progulyai.ru/api/auth/google/callback",
    );
    expect(isAllowedFrontendOrigin("https://progulyai.ru")).toBe(true);
    expect(isAllowedFrontendOrigin("https://evil.example")).toBe(false);

    const { oauthCookieSecure, resolveOAuthRedirectUri } = await import(
      "../src/services/googleOAuth.js"
    );
    expect(oauthCookieSecure("https://localhost:5173")).toBe(true);
    expect(oauthCookieSecure("http://localhost:5173")).toBe(false);
    expect(
      resolveOAuthRedirectUri(
        "https://localhost:5173/api/auth/google/callback",
        "http://localhost:5173",
      ),
    ).toBe("https://localhost:5173/api/auth/google/callback");
  });
});
