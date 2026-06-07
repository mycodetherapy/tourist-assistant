import type { TripPreferences } from "../api/types";
import { DEFAULT_PREFERENCES } from "../components/PreferencesForm";

/** Нормализует значения Ant Design Form перед POST /api/trips. */
export function normalizeTripPreferences(
  raw: Partial<TripPreferences> | null | undefined,
): TripPreferences {
  const rating = raw?.min_restaurant_rating;
  const parsedRating =
    typeof rating === "number"
      ? rating
      : typeof rating === "string"
        ? Number.parseFloat(rating)
        : Number.NaN;

  return {
    ...DEFAULT_PREFERENCES,
    ...raw,
    pace: raw?.pace ?? DEFAULT_PREFERENCES.pace,
    budget: raw?.budget ?? DEFAULT_PREFERENCES.budget,
    transport_preference:
      raw?.transport_preference ?? DEFAULT_PREFERENCES.transport_preference,
    travel_party: raw?.travel_party ?? DEFAULT_PREFERENCES.travel_party,
    interests: Array.isArray(raw?.interests)
      ? raw.interests.map(String).filter(Boolean)
      : DEFAULT_PREFERENCES.interests,
    cuisine: raw?.cuisine ?? DEFAULT_PREFERENCES.cuisine,
    special_notes: raw?.special_notes ?? "",
    min_restaurant_rating:
      Number.isFinite(parsedRating) && parsedRating >= 1 && parsedRating <= 5
        ? parsedRating
        : DEFAULT_PREFERENCES.min_restaurant_rating,
  };
}
