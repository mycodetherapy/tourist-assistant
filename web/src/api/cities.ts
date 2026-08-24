import { apiClient } from "./client";

export interface OsrmReadyCity {
  slug: string;
  display_name: string;
}

export async function fetchOsrmReadyCities(): Promise<OsrmReadyCity[]> {
  const { data } = await apiClient.get<{ cities: OsrmReadyCity[] }>(
    "/cities/osrm-ready",
  );
  return data.cities ?? [];
}
