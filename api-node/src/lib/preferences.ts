import { z } from "zod";

export const routeAnchorSchema = z.object({
  lat: z.number().min(-90).max(90),
  lon: z.number().min(-180).max(180),
  label: z.string().max(500).default(""),
  source: z.enum(["address", "coordinates", "map"]).default("map"),
  loop_end: z.boolean().default(false),
});

export const tripPreferencesSchema = z
  .object({
    pace: z.enum(["relaxed", "moderate", "packed"]).default("packed"),
    budget: z.enum(["economy", "medium", "unlimited"]).default("medium"),
    interests: z.array(z.string()).default([]),
    cuisine: z.string().default(""),
    min_restaurant_rating: z.number().min(1).max(5).default(4),
    transport_preference: z
      .enum(["metro", "taxi", "walking", "mixed"])
      .default("mixed"),
    travel_party: z
      .enum([
        "solo",
        "couple",
        "family",
        "friends",
        "parent_child",
        "family_two",
      ])
      .default("couple"),
    special_notes: z.string().default(""),
    route_anchor: routeAnchorSchema.nullable().optional(),
  })
  .transform((data) => ({
    ...data,
    interests: data.interests ?? [],
  }));

export type TripPreferences = z.infer<typeof tripPreferencesSchema>;

export function normalizeTripPreferences(
  raw: Record<string, unknown> | null | undefined,
): TripPreferences {
  return tripPreferencesSchema.parse({
    pace: "packed",
    budget: "medium",
    transport_preference: "mixed",
    travel_party: "couple",
    interests: [],
    cuisine: "",
    special_notes: "",
    min_restaurant_rating: 4,
    ...raw,
  });
}

export function mergeTripPreferences(
  existing: Record<string, unknown> | null | undefined,
  update: Record<string, unknown>,
): TripPreferences {
  const base = existing ? normalizeTripPreferences(existing) : normalizeTripPreferences({});
  const merged = { ...base, ...update };
  if (update.route_anchor === null) {
    merged.route_anchor = null;
  }
  return normalizeTripPreferences(merged);
}
