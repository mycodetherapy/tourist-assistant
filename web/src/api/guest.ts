import axios, { type AxiosError } from "axios";
import type {
  CityCenter,
  CreateTripPayload,
  CreateTripResponse,
  GeocodeResult,
  ItemFeedbackPayload,
  ProgramResponse,
  RebuildScope,
  RunStatus,
  TripDetail,
  TripPreferences,
  UpdatePreferencesPayload,
} from "./types";
import type { PoiFactResponse } from "./poiFacts";

export const guestClient = axios.create({
  baseURL: "/api/guest",
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

export interface GuestSessionInfo {
  trip_id: number | null;
  full_runs_used: number;
  partial_runs_used: number;
  full_runs_limit: number;
  partial_runs_limit: number;
  expires_at: string;
}

export async function ensureGuestSession(): Promise<GuestSessionInfo> {
  const { data } = await guestClient.post<GuestSessionInfo>("/session");
  return data;
}

export async function fetchGuestSession(): Promise<GuestSessionInfo | null> {
  try {
    const { data } = await guestClient.get<GuestSessionInfo>("/session");
    return data;
  } catch {
    return null;
  }
}

export async function guestFetchTrip(id: number): Promise<TripDetail> {
  const { data } = await guestClient.get<TripDetail>(`/trips/${id}`);
  return data;
}

export async function guestFetchProgram(id: number): Promise<ProgramResponse> {
  const { data } = await guestClient.get<ProgramResponse>(`/trips/${id}/program`);
  return data;
}

export async function guestFetchPreferences(id: number): Promise<TripPreferences | null> {
  const { data } = await guestClient.get<TripPreferences | null>(`/trips/${id}/preferences`);
  return data;
}

export async function guestUpdatePreferences(
  tripId: number,
  payload: UpdatePreferencesPayload,
): Promise<TripPreferences> {
  const { data } = await guestClient.put<TripPreferences>(
    `/trips/${tripId}/preferences`,
    payload,
  );
  return data;
}

export async function guestFetchCityCenter(tripId: number): Promise<CityCenter> {
  const { data } = await guestClient.get<CityCenter>(`/trips/${tripId}/city-center`);
  return data;
}

export async function guestGeocodeAddress(
  tripId: number,
  query: string,
  cityHint = "",
): Promise<{ results: GeocodeResult[] }> {
  const { data } = await guestClient.post<{ results: GeocodeResult[] }>(
    `/trips/${tripId}/geocode`,
    { query, city_hint: cityHint },
  );
  return data;
}

export async function guestGeocodeQuery(
  query: string,
  cityHint: string,
): Promise<{ results: GeocodeResult[] }> {
  const { data } = await guestClient.post<{ results: GeocodeResult[] }>("/trips/geocode", {
    query,
    city_hint: cityHint,
  });
  return data;
}

export async function guestReverseGeocodeAddress(
  tripId: number,
  lat: number,
  lon: number,
  cityHint = "",
): Promise<GeocodeResult> {
  const { data } = await guestClient.post<GeocodeResult>(
    `/trips/${tripId}/reverse-geocode`,
    { lat, lon, city_hint: cityHint },
  );
  return data;
}

export async function guestReverseGeocodeQuery(
  lat: number,
  lon: number,
  cityHint: string,
): Promise<GeocodeResult> {
  const { data } = await guestClient.post<GeocodeResult>("/trips/reverse-geocode", {
    lat,
    lon,
    city_hint: cityHint,
  });
  return data;
}

export async function guestCreateTrip(payload: CreateTripPayload): Promise<CreateTripResponse> {
  const { data } = await guestClient.post<CreateTripResponse>("/trips", payload);
  return data;
}

export async function guestStartRun(
  tripId: number,
  scope: RebuildScope,
  captcha_token?: string,
): Promise<CreateTripResponse> {
  const { data } = await guestClient.post<CreateTripResponse>(`/trips/${tripId}/runs`, {
    scope,
    ...(captcha_token ? { captcha_token } : {}),
  });
  return data;
}

export async function guestFetchRun(runId: string): Promise<RunStatus> {
  const { data } = await guestClient.get<RunStatus>(`/runs/${runId}`);
  return data;
}

export async function guestSubmitItemFeedback(
  tripId: number,
  payload: ItemFeedbackPayload,
): Promise<ProgramResponse> {
  const { data } = await guestClient.put<ProgramResponse>(
    `/trips/${tripId}/program/feedback`,
    payload,
  );
  return data;
}

export async function guestStartPoiFact(
  tripId: number,
  payload: { poi_id?: string | null; name: string },
): Promise<PoiFactResponse> {
  const { data } = await guestClient.post<PoiFactResponse>(
    `/trips/${tripId}/poi-facts`,
    payload,
  );
  return data;
}

export async function guestFetchPoiFact(
  tripId: number,
  cacheKey: string,
): Promise<PoiFactResponse> {
  const { data } = await guestClient.get<PoiFactResponse>(
    `/trips/${tripId}/poi-facts/${encodeURIComponent(cacheKey)}`,
  );
  return data;
}

export function isRegisterRequiredError(error: unknown): boolean {
  if (!axios.isAxiosError(error)) {
    return false;
  }
  const err = error as AxiosError<{ detail?: { code?: string } | string }>;
  if (err.response?.status !== 403) {
    return false;
  }
  const detail = err.response.data?.detail;
  return (
    typeof detail === "object" &&
    detail !== null &&
    detail.code === "register_required"
  );
}

export function getRegisterRequiredMessage(error: unknown): string | null {
  if (!isRegisterRequiredError(error)) return null;
  const err = error as AxiosError<{ detail?: { message?: string } }>;
  const detail = err.response?.data?.detail;
  if (typeof detail === "object" && detail?.message) {
    return detail.message;
  }
  return "Зарегистрируйтесь, чтобы продолжить";
}

export function isCaptchaError(error: unknown): boolean {
  if (!axios.isAxiosError(error)) {
    return false;
  }
  const err = error as AxiosError<{ detail?: { code?: string } | string }>;
  const status = err.response?.status;
  if (status !== 400 && status !== 403 && status !== 503) {
    return false;
  }
  const detail = err.response.data?.detail;
  return (
    typeof detail === "object" &&
    detail !== null &&
    (detail.code === "captcha_required" ||
      detail.code === "captcha_failed" ||
      detail.code === "captcha_unavailable")
  );
}

export function getCaptchaErrorMessage(error: unknown): string | null {
  if (!isCaptchaError(error)) return null;
  const err = error as AxiosError<{ detail?: { message?: string } }>;
  const detail = err.response?.data?.detail;
  if (typeof detail === "object" && detail?.message) {
    return detail.message;
  }
  return "Не удалось пройти проверку CAPTCHA";
}
