import { getUserLlmMode, type LlmMode } from "./auth.js";
import { config } from "../config.js";
import { getUserSettings } from "../repos/users.js";

/** Лимит 3 города — только бесплатный режим. BYOK с сохранённым ключом без квоты. */
export function osrmPrepareQuotaUnlimited(
  mode: LlmMode,
  keyConfigured: boolean,
): boolean {
  return mode === "byok" && keyConfigured;
}

export async function resolveOsrmPrepareQuota(userId: number): Promise<{
  unlimited: boolean;
  limit: number;
}> {
  const mode = await getUserLlmMode(userId);
  const settings = await getUserSettings(userId);
  return {
    unlimited: osrmPrepareQuotaUnlimited(mode, Boolean(settings?.llm_api_key_enc)),
    limit: config.osrmPrepareQuotaPerUser,
  };
}
