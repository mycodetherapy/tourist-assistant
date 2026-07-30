import { apiClient } from "./client";
import type { AuthResponse, UserInfo } from "./types";

export async function login(email: string, password: string): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>("/auth/login", { email, password });
  return data;
}

export async function register(email: string, password: string): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>("/auth/register", { email, password });
  return data;
}

export async function fetchMe(): Promise<UserInfo> {
  const { data } = await apiClient.get<UserInfo>("/auth/me");
  return data;
}

export function googleLoginUrl(): string {
  const frontend = encodeURIComponent(window.location.origin);
  return `/api/auth/google?frontend=${frontend}`;
}
