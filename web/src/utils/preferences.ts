import type { LeisureTag, TripPreferences } from "../api/types";
import { DEFAULT_PREFERENCES } from "../components/PreferencesForm";

const ALL_LEISURE: LeisureTag[] = [
  "landmarks",
  "museums",
  "exhibitions",
  "galleries",
  "philharmonic",
  "theaters",
  "parks",
];

export function normalizeLeisureCategories(raw: unknown): LeisureTag[] {
  const selected = Array.isArray(raw)
    ? raw.map(String).filter((tag): tag is LeisureTag => ALL_LEISURE.includes(tag as LeisureTag))
    : [];
  const withLandmarks = selected.includes("landmarks")
    ? selected
    : (["landmarks", ...selected] as LeisureTag[]);
  return [...new Set(withLandmarks)];
}

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
    leisure_categories: normalizeLeisureCategories(
      raw?.leisure_categories ?? DEFAULT_PREFERENCES.leisure_categories,
    ),
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
