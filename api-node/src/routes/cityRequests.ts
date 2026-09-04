import type { FastifyInstance, FastifyRequest } from "fastify";
import { z } from "zod";
import { query } from "../db/pool.js";
import { resolveRequestUser } from "../middleware/auth.js";
import {
  InputValidationError,
  sanitizeAndValidate,
} from "../lib/inputValidation.js";

const bodySchema = z.object({
  city_name: z.string().min(1).max(500),
  email: z.string().email().max(320).optional().or(z.literal("")),
});

function normalizeCityName(name: string): string {
  return name.trim().toLowerCase().replace(/\s+/g, " ");
}

async function optionalUserId(request: FastifyRequest): Promise<number | null> {
  try {
    const user = await resolveRequestUser(request);
    return user?.id ?? null;
  } catch {
    return null;
  }
}

type CityRequestRow = {
  id: string | number;
  city_name: string;
  normalized_name: string;
  email: string | null;
  user_id: string | number | null;
  status: string;
  request_count: number;
  note: string | null;
  created_at: Date | string;
  updated_at: Date | string;
};

function view(row: CityRequestRow) {
  return {
    id: Number(row.id),
    city_name: row.city_name,
    normalized_name: row.normalized_name,
    email: row.email,
    user_id: row.user_id == null ? null : Number(row.user_id),
    status: row.status,
    request_count: Number(row.request_count),
    note: row.note,
    created_at:
      row.created_at instanceof Date
        ? row.created_at.toISOString()
        : String(row.created_at),
    updated_at:
      row.updated_at instanceof Date
        ? row.updated_at.toISOString()
        : String(row.updated_at),
  };
}

export async function registerCityRequestRoutes(
  app: FastifyInstance,
): Promise<void> {
  app.post("/api/city-requests", async (request, reply) => {
    const parsed = bodySchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ detail: "Некорректные данные" });
    }

    let cityName: string;
    try {
      cityName = sanitizeAndValidate(parsed.data.city_name, "city");
    } catch (err) {
      if (err instanceof InputValidationError) {
        return reply.code(400).send({ detail: err.message });
      }
      throw err;
    }

    const emailRaw = (parsed.data.email || "").trim();
    const email = emailRaw || null;
    const normalized = normalizeCityName(cityName);
    const userId = await optionalUserId(request);

    const existing = await query<CityRequestRow>(
      `SELECT id, city_name, normalized_name, email, user_id, status,
              request_count, note, created_at, updated_at
       FROM city_requests WHERE normalized_name = $1 LIMIT 1`,
      [normalized],
    );

    if (existing.rowCount && existing.rows[0]) {
      const row = existing.rows[0];
      const nextStatus = row.status === "rejected" ? "new" : row.status;
      const updated = await query<CityRequestRow>(
        `UPDATE city_requests
         SET request_count = request_count + 1,
             updated_at = now(),
             status = $2,
             email = COALESCE(email, $3),
             user_id = COALESCE(user_id, $4)
         WHERE id = $1
         RETURNING id, city_name, normalized_name, email, user_id, status,
                   request_count, note, created_at, updated_at`,
        [row.id, nextStatus, email, userId],
      );
      return reply.code(200).send(view(updated.rows[0]!));
    }

    const inserted = await query<CityRequestRow>(
      `INSERT INTO city_requests
         (city_name, normalized_name, email, user_id, status, request_count)
       VALUES ($1, $2, $3, $4, 'new', 1)
       RETURNING id, city_name, normalized_name, email, user_id, status,
                 request_count, note, created_at, updated_at`,
      [cityName, normalized, email, userId],
    );
    return reply.code(201).send(view(inserted.rows[0]!));
  });
}
