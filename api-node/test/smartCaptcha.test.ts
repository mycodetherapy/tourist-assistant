import { randomBytes } from "node:crypto";
import { describe, expect, it, vi, afterEach } from "vitest";

process.env.JWT_SECRET = "test-jwt-secret-for-unit-tests-only";
process.env.SETTINGS_ENCRYPTION_KEY = randomBytes(32).toString("base64url");

const { SmartCaptchaError, verifySmartCaptchaToken, assertGuestCaptcha, smartCaptchaConfigured } =
  await import("../src/services/smartCaptcha.js");

describe("smartCaptcha", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.YANDEX_SMARTCAPTCHA_SERVER_KEY;
  });

  it("smartCaptchaConfigured is false without server key", () => {
    expect(smartCaptchaConfigured()).toBe(false);
  });

  it("verifySmartCaptchaToken skips when server key unset", async () => {
    await expect(verifySmartCaptchaToken("token", "127.0.0.1")).resolves.toBeUndefined();
  });

  it("verifySmartCaptchaToken accepts ok response", async () => {
    process.env.YANDEX_SMARTCAPTCHA_SERVER_KEY = "ysc2_test";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "ok" }),
      }),
    );
    await expect(verifySmartCaptchaToken("good-token", "1.2.3.4")).resolves.toBeUndefined();
    expect(fetch).toHaveBeenCalledWith(
      "https://smartcaptcha.cloud.yandex.ru/validate",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("verifySmartCaptchaToken rejects failed validation", async () => {
    process.env.YANDEX_SMARTCAPTCHA_SERVER_KEY = "ysc2_test";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "failed" }),
      }),
    );
    await expect(verifySmartCaptchaToken("bad-token", "1.2.3.4")).rejects.toMatchObject({
      code: "captcha_failed",
    });
  });

  it("assertGuestCaptcha requires token when configured", async () => {
    process.env.YANDEX_SMARTCAPTCHA_SERVER_KEY = "ysc2_test";
    const request = { ip: "127.0.0.1", headers: {} } as Parameters<
      typeof assertGuestCaptcha
    >[0];
    await expect(assertGuestCaptcha(request, undefined)).rejects.toBeInstanceOf(
      SmartCaptchaError,
    );
    await expect(assertGuestCaptcha(request, "  ")).rejects.toMatchObject({
      code: "captcha_required",
    });
  });
});
