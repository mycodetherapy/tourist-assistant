import { apiClient } from "./client";
import type {
  CreateTripPayload,
  CreateTripResponse,
  ItemFeedbackPayload,
  ProfileResponse,
  ProgramResponse,
  ReviewAction,
  ReviewResponse,
  RebuildScope,
  RunStatus,
  TripDetail,
  TripPreferences,
  TripSummary,
} from "./types";

export async function fetchTrips(): Promise<TripSummary[]> {
  const { data } = await apiClient.get<TripSummary[]>("/trips");
  return data;
}

export async function fetchTrip(id: number): Promise<TripDetail> {
  const { data } = await apiClient.get<TripDetail>(`/trips/${id}`);
  return data;
}

export async function fetchProgram(id: number): Promise<ProgramResponse> {
  const { data } = await apiClient.get<ProgramResponse>(`/trips/${id}/program`);
  return data;
}

export async function logAffiliateClick(tripId: number, targetUrl: string): Promise<void> {
  await apiClient.post(`/trips/${tripId}/affiliate-clicks`, { target_url: targetUrl });
}

export async function submitItemFeedback(
  tripId: number,
  payload: ItemFeedbackPayload,
): Promise<ProgramResponse> {
  const { data } = await apiClient.put<ProgramResponse>(
    `/trips/${tripId}/program/feedback`,
    payload,
  );
  return data;
}

export async function fetchProfile(): Promise<ProfileResponse> {
  const { data } = await apiClient.get<ProfileResponse>("/profile");
  return data;
}

export async function fetchPreferences(id: number): Promise<TripPreferences | null> {
  const { data } = await apiClient.get<TripPreferences | null>(`/trips/${id}/preferences`);
  return data;
}

export async function createTrip(payload: CreateTripPayload): Promise<CreateTripResponse> {
  const { data } = await apiClient.post<CreateTripResponse>("/trips", payload);
  return data;
}

export async function startRun(tripId: number, scope: RebuildScope): Promise<CreateTripResponse> {
  const { data } = await apiClient.post<CreateTripResponse>(`/trips/${tripId}/runs`, { scope });
  return data;
}

export async function fetchRun(runId: string): Promise<RunStatus> {
  const { data } = await apiClient.get<RunStatus>(`/runs/${runId}`);
  return data;
}

export async function deleteTrip(tripId: number): Promise<void> {
  await apiClient.delete(`/trips/${tripId}`);
}

export async function submitReview(
  tripId: number,
  action: ReviewAction,
): Promise<ReviewResponse> {
  const { data } = await apiClient.post<ReviewResponse>(`/trips/${tripId}/review`, { action });
  return data;
}
