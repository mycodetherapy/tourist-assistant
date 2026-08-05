import type { FastifyRequest } from "fastify";
import { config } from "../config.js";

const VALIDATE_URL = "https://smartcaptcha.cloud.yandex.ru/validate";

export class SmartCaptchaError extends Error {
  readonly code: "captcha_required" | "captcha_failed" | "captcha_unavailable";

  constructor(
    message: string,
    code: "captcha_required" | "captcha_failed" | "captcha_unavailable",
  ) {
    super(message);
    this.code = code;
  }
}

export function smartCaptchaConfigured(): boolean {
  return Boolean(config.yandexSmartCaptchaServerKey());
}

export function clientIp(request: FastifyRequest): string {
  const forwarded = request.headers["x-forwarded-for"];
  if (typeof forwarded === "string" && forwarded.trim()) {
    return forwarded.split(",")[0]!.trim();
  }
  return request.ip;
}

export async function verifySmartCaptchaToken(
  token: string,
  ip: string,
): Promise<void> {
  const secret = config.yandexSmartCaptchaServerKey();
  if (!secret) {
    return;
  }
  const body = new URLSearchParams({
    secret,
    token,
    ip,
  });
  let response: Response;
  try {
    response = await fetch(VALIDATE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    throw new SmartCaptchaError(
      "Проверка CAPTCHA временно недоступна. Попробуйте позже.",
      "captcha_unavailable",
    );
  }
  if (!response.ok) {
    throw new SmartCaptchaError(
      "Проверка CAPTCHA временно недоступна. Попробуйте позже.",
      "captcha_unavailable",
    );
  }
  const payload = (await response.json()) as { status?: string; message?: string };
  if (payload.status !== "ok") {
    throw new SmartCaptchaError(
      "Подтвердите, что вы не робот, и попробуйте снова.",
      "captcha_failed",
    );
  }
}

export async function assertGuestCaptcha(
  request: FastifyRequest,
  token: string | undefined,
): Promise<void> {
  if (!smartCaptchaConfigured()) {
    return;
  }
  const trimmed = token?.trim();
  if (!trimmed) {
    throw new SmartCaptchaError(
      "Требуется проверка CAPTCHA",
      "captcha_required",
    );
  }
  await verifySmartCaptchaToken(trimmed, clientIp(request));
}
