import { apiClient } from "./client";

export type OsrmEligibleCity = {
  slug: string;
  display_name: string;
  federal_district: string;
};

export type OsrmPrepareJob = {
  id: string;
  user_id: number;
  slug: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  stage: string;
  progress: number;
  error: string | null;
  counts_against_quota: boolean;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
};

export async function fetchOsrmEligibleCities(): Promise<{
  cities: OsrmEligibleCity[];
  quota_limit: number;
}> {
  const { data } = await apiClient.get<{
    cities: OsrmEligibleCity[];
    quota_limit: number;
  }>("/cities/osrm-eligible");
  return data;
}

export async function startOsrmPrepare(slug: string): Promise<{
  job: OsrmPrepareJob;
  joined?: boolean;
}> {
  const { data } = await apiClient.post<{ job: OsrmPrepareJob; joined?: boolean }>(
    "/osrm-prepares",
    { slug },
  );
  return data;
}

export async function fetchOsrmPrepareJob(id: string): Promise<OsrmPrepareJob> {
  const { data } = await apiClient.get<{ job: OsrmPrepareJob }>(`/osrm-prepares/${id}`);
  return data.job;
}

export async function fetchMyOsrmPrepares(): Promise<{
  jobs: OsrmPrepareJob[];
  quota_used: number;
  quota_limit: number;
}> {
  const { data } = await apiClient.get<{
    jobs: OsrmPrepareJob[];
    quota_used: number;
    quota_limit: number;
  }>("/osrm-prepares");
  return data;
}
