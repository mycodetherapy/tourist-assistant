export type RebuildScope = "full" | "tickets" | "events" | "dining" | "lifehacks";
export type ReviewAction = "approve" | "save_draft" | "rebuild";
export type RunStatusName = "queued" | "running" | "completed" | "failed";

export interface TripSummary {
  id: number;
  city: string;
  dates: string;
  origin_city: string;
  status: string;
  updated_at: string;
}

export interface TripDetail {
  id: number;
  city: string;
  dates: string;
  origin_city: string;
  user_query: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface TripPreferences {
  pace: "relaxed" | "moderate" | "packed";
  budget: "economy" | "medium" | "unlimited";
  interests: string[];
  cuisine: string;
  min_restaurant_rating: number;
  transport_preference: "metro" | "taxi" | "walking" | "mixed";
  travel_party: "solo" | "couple" | "family" | "friends";
  special_notes: string;
}

export interface FinalProgram {
  tickets: string;
  events: string;
  dining: string;
  lifehacks: string;
}

export interface ProgramResponse {
  version: number;
  scope: string;
  approved: boolean;
  program: FinalProgram;
}

export interface CreateTripPayload {
  city: string;
  dates: string;
  origin_city: string;
  user_query: string;
  preferences: TripPreferences;
  start_run: boolean;
}

export interface CreateTripResponse {
  trip_id: number;
  run_id: string | null;
}

export interface RunStatus {
  run_id: string;
  trip_id: number;
  status: RunStatusName;
  error: string | null;
  version_id: number | null;
}

export interface ReviewResponse {
  trip_id: number;
  status: string;
  run_id: string | null;
}

export interface ProfileResponse {
  preferences: TripPreferences | null;
}
