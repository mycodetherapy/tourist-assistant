import axios, { type AxiosError } from "axios";

const LEGACY_TOKEN_KEY = "tourist_auth_token";

function readLegacyToken(): string | null {
  try {
    return localStorage.getItem(LEGACY_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function clearLegacyAuthToken(): void {
  try {
    localStorage.removeItem(LEGACY_TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export const apiClient = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  const token = readLegacyToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function isLlmKeyRequiredError(error: unknown): boolean {
  if (!axios.isAxiosError(error)) {
    return false;
  }
  const err = error as AxiosError<{ detail?: { code?: string } | string }>;
  if (err.response?.status !== 428) {
    return false;
  }
  const detail = err.response.data?.detail;
  if (typeof detail === "object" && detail !== null && detail.code === "llm_key_required") {
    return true;
  }
  return false;
}

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "object" && detail !== null && "message" in detail) {
      return String((detail as { message: string }).message);
    }
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          if (typeof d !== "object" || d === null) return String(d);
          const loc = Array.isArray(d.loc) ? d.loc.join(".") : "";
          const msg = d.msg ?? String(d);
          return loc ? `${loc}: ${msg}` : msg;
        })
        .join("; ");
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Неизвестная ошибка";
}
