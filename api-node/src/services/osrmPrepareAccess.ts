import type { LlmMode } from "./auth.js";

export type OsrmPrepareLockCode = "free_mode" | "need_key" | "platform";

export type OsrmPrepareLock = {
  code: OsrmPrepareLockCode;
  message: string;
};

export function getOsrmPrepareLock(
  mode: LlmMode,
  keyConfigured: boolean,
): OsrmPrepareLock | null {
  if (mode === "none") {
    return {
      code: "free_mode",
      message:
        "В бесплатном режиме нельзя готовить новые города на карте — это нагрузка на сервер. Включите «Свой API-ключ (BYOK)» ниже, укажите ключ при необходимости и нажмите «Сохранить».",
    };
  }
  if (mode === "platform") {
    return {
      code: "platform",
      message:
        "Оплата AI из приложения скоро будет доступна. Пока используйте свой API-ключ, чтобы готовить города.",
    };
  }
  if (!keyConfigured) {
    return {
      code: "need_key",
      message:
        "Чтобы готовить города на карте, сохраните API-ключ провайдера в режиме «Свой API-ключ».",
    };
  }
  return null;
}
