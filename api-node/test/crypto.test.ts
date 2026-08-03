import { randomBytes } from "node:crypto";
import { describe, expect, it, vi } from "vitest";

process.env.JWT_SECRET = "test-jwt-secret-for-unit-tests-only";
process.env.SETTINGS_ENCRYPTION_KEY = randomBytes(32).toString("base64url");

const { encryptSecret, decryptSecret, createAccessToken, decodeAccessToken } =
  await import("../src/lib/crypto.js");

describe("crypto", () => {
  it("roundtrips fernet secret", () => {
    const plain = "sk-or-v1-test-key-abcdefghijklmnop";
    const enc = encryptSecret(plain);
    expect(decryptSecret(enc)).toBe(plain);
  });

  it("jwt encode/decode", () => {
    const token = createAccessToken(42, "user@example.com");
    const payload = decodeAccessToken(token);
    expect(payload.sub).toBe("42");
    expect(payload.email).toBe("user@example.com");
  });

  it("jwt tolerates invalid JWT_ACCESS_TTL_MINUTES", async () => {
    vi.resetModules();
    process.env.JWT_ACCESS_TTL_MINUTES = "not-a-number";
    process.env.JWT_SECRET = "test-jwt-secret-for-unit-tests-only";
    process.env.SETTINGS_ENCRYPTION_KEY = randomBytes(32).toString("base64url");
    const { createAccessToken: create, decodeAccessToken: decode } =
      await import("../src/lib/crypto.js");
    const token = create(1, "a@b.co");
    expect(decode(token).sub).toBe("1");
  });
});
