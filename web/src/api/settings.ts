import { apiClient } from "./client";
import type { SettingsResponse, UpdateSettingsPayload } from "./types";

export async function fetchSettings(): Promise<SettingsResponse> {
  const { data } = await apiClient.get<SettingsResponse>("/profile/settings");
  return data;
}

export async function updateSettings(payload: UpdateSettingsPayload): Promise<SettingsResponse> {
  const { data } = await apiClient.put<SettingsResponse>("/profile/settings", payload);
  return data;
}

export async function deleteLlmKey(): Promise<void> {
  await apiClient.delete("/profile/settings/llm-key");
}
