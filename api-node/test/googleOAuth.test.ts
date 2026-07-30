import "./setup-env.js";

import { describe, expect, it } from "vitest";

async function loadGoogleOAuth() {
  process.env.GOOGLE_CLIENT_ID = "test-client-id";
  process.env.GOOGLE_CLIENT_SECRET = "test-client-secret";
  return import("../src/services/googleOAuth.js");
}

describe("googleOAuth", () => {
  it("signs and verifies state", async () => {
    process.env.FRONTEND_URL = "https://localhost:5173";
    process.env.CORS_ORIGINS = "";
    const { buildGoogleAuthorizeUrl, verifyOAuthState } = await loadGoogleOAuth();

    const https = buildGoogleAuthorizeUrl("https://localhost:5173");
    expect(verifyOAuthState(https.state)).toBe(true);
    expect(verifyOAuthState("bad")).toBe(false);
    expect(https.url).toContain(encodeURIComponent(https.redirectUri));
  });

  it("canonicalizes local dev origins", async () => {
    process.env.FRONTEND_URL = "https://localhost:5173";
    process.env.CORS_ORIGINS = "";
    const { buildGoogleAuthorizeUrl } = await loadGoogleOAuth();

    expect(buildGoogleAuthorizeUrl("http://localhost:5173").redirectUri).toBe(
      "https://localhost:5173/api/auth/google/callback",
    );
    expect(buildGoogleAuthorizeUrl("https://127.0.0.1:5173").redirectUri).toBe(
      "https://localhost:5173/api/auth/google/callback",
    );
    expect(buildGoogleAuthorizeUrl("https://192.168.1.81:5173").redirectUri).toBe(
      "https://192.168.1.81:5173/api/auth/google/callback",
    );
  });

  it("uses prod redirect URI from configured origin", async () => {
    process.env.FRONTEND_URL = "https://progulyai.ru";
    process.env.CORS_ORIGINS = "https://progulyai.ru";
    const { buildGoogleAuthorizeUrl } = await loadGoogleOAuth();

    expect(buildGoogleAuthorizeUrl("https://progulyai.ru").redirectUri).toBe(
      "https://progulyai.ru/api/auth/google/callback",
    );
  });

  it("rejects untrusted frontend origins", async () => {
    process.env.FRONTEND_URL = "https://progulyai.ru";
    process.env.CORS_ORIGINS = "https://progulyai.ru";
    const {
      buildGoogleAuthorizeUrl,
      isAllowedFrontendOrigin,
      isAllowedRedirectUri,
      oauthRedirectOrigin,
      resolveFrontendUrl,
      resolveOAuthRedirectUri,
    } = await loadGoogleOAuth();

    expect(isAllowedFrontendOrigin("https://evil.example")).toBe(false);
    expect(isAllowedFrontendOrigin("https://attacker.com")).toBe(false);
    expect(isAllowedFrontendOrigin("https://999.999.999.999:5173")).toBe(false);

    expect(resolveFrontendUrl("https://attacker.com", undefined)).toBe(
      "https://progulyai.ru",
    );
    expect(resolveFrontendUrl(undefined, "https://attacker.com")).toBe(
      "https://progulyai.ru",
    );

    expect(oauthRedirectOrigin("https://attacker.com")).toBe("https://progulyai.ru");
    expect(buildGoogleAuthorizeUrl("https://attacker.com").redirectUri).toBe(
      "https://progulyai.ru/api/auth/google/callback",
    );

    expect(
      isAllowedRedirectUri("https://attacker.com/api/auth/google/callback"),
    ).toBe(false);
    expect(
      resolveOAuthRedirectUri(
        "https://attacker.com/api/auth/google/callback",
        "https://progulyai.ru",
      ),
    ).toBe("https://progulyai.ru/api/auth/google/callback");
  });

  it("does not canonicalize loopback with different ports", async () => {
    process.env.FRONTEND_URL = "https://localhost:5173";
    process.env.CORS_ORIGINS = "";
    const { oauthRedirectOrigin } = await loadGoogleOAuth();

    expect(oauthRedirectOrigin("https://localhost:8080")).toBe(
      "https://localhost:8080",
    );
  });

  it("oauth cookie secure flag follows frontend protocol", async () => {
    process.env.FRONTEND_URL = "https://localhost:5173";
    const { oauthCookieSecure, resolveOAuthRedirectUri } = await loadGoogleOAuth();

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
