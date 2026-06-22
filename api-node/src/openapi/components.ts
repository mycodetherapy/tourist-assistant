import { zodToJsonSchema } from "zod-to-json-schema";
import { z } from "zod";
import { routeAnchorSchema } from "../lib/preferences.js";

/** Общие Zod-схемы запросов/ответов (источник правды для OpenAPI). */

export const registerBodySchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

export const loginBodySchema = registerBodySchema;

export const authResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.literal("bearer"),
  user: z.object({
    id: z.number().int(),
    email: z.string().email(),
  }),
});

export const userResponseSchema = z.object({
  id: z.number().int(),
  email: z.string().email(),
});

export const errorDetailSchema = z.object({
  detail: z.union([z.string(), z.record(z.unknown())]),
});

export const settingsBodySchema = z.object({
  llm_api_key: z.string().max(256).nullable().optional(),
  llm_base_url: z.string().max(512).nullable().optional(),
  llm_model: z.string().max(128).nullable().optional(),
});

export const createTripBodySchema = z.object({
  city: z.string().min(1),
  route_anchor: routeAnchorSchema.nullable().optional(),
  user_query: z.string().default("Составь три варианта маршрута по городу"),
  preferences: z.record(z.unknown()).nullable().optional(),
  start_run: z.boolean().default(true),
});

export const createTripResponseSchema = z.object({
  trip_id: z.number().int(),
  run_id: z.string().nullable(),
});

export const tripSummarySchema = z.object({
  id: z.number().int(),
  city: z.string(),
  updated_at: z.string(),
});

export const startRunBodySchema = z.object({
  scope: z.enum(["routes", "full"]).default("routes"),
});

export const runStatusSchema = z.object({
  run_id: z.string(),
  trip_id: z.number().int(),
  status: z.enum(["queued", "running", "completed", "failed"]),
  error: z.string().nullable(),
  version_id: z.number().int().nullable(),
  city_fact_status: z.enum([
    "pending",
    "ready",
    "failed",
    "skipped",
    "idle",
  ]),
});

export const geocodeBodySchema = z.object({
  query: z.string().min(2).max(500),
  city_hint: z.string().max(128).default(""),
});

export const geocodeResultSchema = z.object({
  lat: z.number(),
  lon: z.number(),
  label: z.string(),
});

export const healthSchema = z.object({
  status: z.literal("ok"),
});

function asComponent(name: string, schema: z.ZodTypeAny) {
  return zodToJsonSchema(schema, {
    name,
    $refStrategy: "none",
    target: "openApi3",
  });
}

export const openApiComponents = {
  securitySchemes: {
    bearerAuth: {
      type: "http" as const,
      scheme: "bearer",
      bearerFormat: "JWT",
      description: "JWT из POST /api/auth/login или /api/auth/register",
    },
  },
  schemas: {
    RegisterRequest: asComponent("RegisterRequest", registerBodySchema),
    LoginRequest: asComponent("LoginRequest", loginBodySchema),
    AuthResponse: asComponent("AuthResponse", authResponseSchema),
    UserResponse: asComponent("UserResponse", userResponseSchema),
    ErrorDetail: asComponent("ErrorDetail", errorDetailSchema),
    UpdateSettingsRequest: asComponent(
      "UpdateSettingsRequest",
      settingsBodySchema,
    ),
    CreateTripRequest: asComponent("CreateTripRequest", createTripBodySchema),
    CreateTripResponse: asComponent(
      "CreateTripResponse",
      createTripResponseSchema,
    ),
    TripSummary: asComponent("TripSummary", tripSummarySchema),
    StartRunRequest: asComponent("StartRunRequest", startRunBodySchema),
    RunStatusResponse: asComponent("RunStatusResponse", runStatusSchema),
    GeocodeRequest: asComponent("GeocodeRequest", geocodeBodySchema),
    GeocodeResult: asComponent("GeocodeResult", geocodeResultSchema),
    HealthResponse: asComponent("HealthResponse", healthSchema),
  },
};

export const bearerSecurity = [{ bearerAuth: [] }] as const;

export function ref(name: keyof typeof openApiComponents.schemas) {
  return { $ref: `${name}#` };
}
