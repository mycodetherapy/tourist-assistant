import { apiClient } from "./client";

export type PoiFactStatus = "pending" | "ready" | "failed";

export interface PoiFactResponse {
  cache_key: string;
  name: string;
  status: PoiFactStatus;
  text: string | null;
  error: string | null;
}

export async function startPoiFact(
  tripId: number,
  payload: { poi_id?: string | null; name: string },
): Promise<PoiFactResponse> {
  const { data } = await apiClient.post<PoiFactResponse>(
    `/trips/${tripId}/poi-facts`,
    payload,
  );
  return data;
}

export async function fetchPoiFact(
  tripId: number,
  cacheKey: string,
): Promise<PoiFactResponse> {
  const { data } = await apiClient.get<PoiFactResponse>(
    `/trips/${tripId}/poi-facts/${encodeURIComponent(cacheKey)}`,
  );
  return data;
}
