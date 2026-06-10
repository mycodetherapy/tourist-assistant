export type RebuildScope =
  | "full"
  | "tickets"
  | "routes"
  | "lifehacks"
  | "events"
  | "dining";
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
  travel_party: "solo" | "couple" | "family" | "friends" | "parent_child" | "family_two";
  special_notes: string;
}

import type { RouteProgram } from "./routeTypes";

export interface FinalProgram {
  tickets: string;
  routes?: RouteProgram | null;
  routes_text?: string;
  lifehacks: string;
  events?: string;
  dining?: string;
}

export type ProgramSectionKey =
  | "tickets"
  | "routes"
  | "lifehacks"
  | "events"
  | "dining";
export type VotableSectionKey = "routes" | "route_stops" | "lifehacks" | "events" | "dining";
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
  tickets: ProgramSection;
  routes: ProgramSection;
  route_stops: ProgramSection;
  lifehacks: ProgramSection;
  events: ProgramSection;
  dining: ProgramSection;
}

export interface ProgramResponse {
  version: number;
  version_id: number;
  scope: string;
  approved: boolean;
  program: FinalProgram;
  sections: StructuredProgram;
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
