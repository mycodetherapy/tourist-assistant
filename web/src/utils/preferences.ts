import type { TripPreferences } from "../api/types";

export const DEFAULT_USER_QUERY = "Составь культурную программу поездки";

/** Скрытые defaults; в форме только travel_party. */
export const DEFAULT_PREFERENCES: TripPreferences = {
  pace: "packed",
  budget: "medium",
  interests: [],
  cuisine: "",
  min_restaurant_rating: 4.0,
  transport_preference: "mixed",
  travel_party: "couple",
  special_notes: "",
};

const TRAVEL_PARTIES = new Set<TripPreferences["travel_party"]>([
  "solo",
  "couple",
  "family",
  "friends",
  "parent_child",
  "family_two",
]);

/** Нормализует значения формы: скрытые поля — фиксированные defaults. */
export function normalizeTripPreferences(
  raw: Partial<TripPreferences> | null | undefined,
): TripPreferences {
  const party = raw?.travel_party;
  const travel_party =
    party && TRAVEL_PARTIES.has(party) ? party : DEFAULT_PREFERENCES.travel_party;

  return {
    ...DEFAULT_PREFERENCES,
    travel_party,
  };
}
