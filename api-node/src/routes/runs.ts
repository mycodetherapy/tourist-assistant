import type { FastifyInstance } from "fastify";
import { requireAuth } from "../middleware/auth.js";
import { bearerSecurity, ref } from "../openapi/components.js";
import { tripBelongsToUser } from "../repos/trips.js";
import { getRunStatus } from "../services/runManager.js";

export async function registerRunsRoutes(app: FastifyInstance): Promise<void> {
  app.get<{ Params: { run_id: string } }>(
    "/api/runs/:run_id",
    {
      preHandler: requireAuth,
      schema: {
        tags: ["runs"],
        summary: "Run status",
        security: [...bearerSecurity],
        params: {
          type: "object",
          required: ["run_id"],
          properties: { run_id: { type: "string", format: "uuid" } },
        },
        response: {
          200: ref("RunStatusResponse"),
          404: ref("ErrorDetail"),
        },
      },
    },
    async (request, reply) => {
      const record = await getRunStatus(request.params.run_id);
      if (!record) {
        return reply.code(404).send({ detail: "Прогон не найден" });
      }
      if (!(await tripBelongsToUser(record.trip_id, request.user!.id))) {
        return reply.code(404).send({ detail: "Прогон не найден" });
      }
      return {
        run_id: record.run_id,
        trip_id: record.trip_id,
        status: record.status,
        error: record.error,
        version_id: record.version_id,
        city_fact_status: record.city_fact_status,
      };
    },
  );
}
