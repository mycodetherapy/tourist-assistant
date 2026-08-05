export type RebuildScope = "routes" | "full";
export type RunStatusName = "queued" | "running" | "completed" | "failed";
export type CityFactStatusName = "pending" | "ready" | "failed" | "skipped" | "idle";

export interface TripSummary {
  id: number;
  city: string;
  updated_at: string;
}

export interface TripDetail {
  id: number;
  city: string;
  user_query: string | null;
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
  travel_party: "solo" | "couple" | "family" | "friends" | "parent_child" | "family_two";
  special_notes: string;
  route_anchor?: RouteAnchor | null;
}

export type RouteAnchorSource = "address" | "coordinates" | "map";

export interface RouteAnchor {
  lat: number;
  lon: number;
  label: string;
  source: RouteAnchorSource;
  loop_end: boolean;
}

export interface GeocodeResult {
  lat: number;
  lon: number;
  label: string;
}

export interface CityCenter {
  lat: number;
  lon: number;
  label: string;
}

import type { RouteProgram } from "./routeTypes";

export interface FinalProgram {
  routes?: RouteProgram | null;
  routes_text?: string;
  lifehacks: string;
}

export type ProgramSectionKey = "routes" | "lifehacks";
export type VotableSectionKey = "routes" | "route_stops";
export type ItemVote = 1 | -1;

export interface ProgramItem {
  index: number;
  item_key: string;
  text: string;
  vote: ItemVote | null;
  poi_id?: string | null;
}

export interface ProgramSection {
  intro: string;
  items: ProgramItem[];
}

export interface StructuredProgram {
  routes: ProgramSection;
  route_stops: ProgramSection;
  lifehacks: ProgramSection;
}

export interface ProgramResponse {
  version: number;
  version_id: number;
  scope: string;
  approved: boolean;
  program: FinalProgram;
  sections: StructuredProgram;
  data_warnings?: string[];
  city_fact_status?: CityFactStatusName;
}

export interface ItemFeedbackPayload {
  version_id: number;
  section: VotableSectionKey;
  item_key: string;
  item_index: number;
  vote: ItemVote | null;
}

export interface CreateTripPayload {
  city: string;
  user_query: string;
  route_anchor?: RouteAnchor | null;
  preferences?: TripPreferences | null;
  start_run: boolean;
  captcha_token?: string;
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
  city_fact_status?: CityFactStatusName;
}

export interface ProfileResponse {
  preferences: TripPreferences | null;
}

export interface UserInfo {
  id: number;
  email: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
  claimed_trip_id?: number;
}

export type LlmMode = "none" | "platform" | "byok";

export interface SettingsResponse {
  llm_mode: LlmMode;
  llm_key_configured: boolean;
  llm_key_preview: string | null;
  llm_base_url: string;
  llm_model: string;
  estimated_ai_run_cost_rub: number;
}

export interface UpdateSettingsPayload {
  llm_mode?: LlmMode;
  llm_api_key?: string;
  llm_base_url?: string;
  llm_model?: string;
}

export interface UpdatePreferencesPayload {
  travel_party?: TripPreferences["travel_party"];
  route_anchor?: RouteAnchor | null;
}
