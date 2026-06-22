import { randomBytes } from "node:crypto";
import { beforeAll, describe, expect, it } from "vitest";

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
});
