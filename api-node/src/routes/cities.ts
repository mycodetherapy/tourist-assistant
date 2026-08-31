import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { config } from "../config.js";
import { bearerSecurity, ref } from "../openapi/components.js";
import { requireAuth } from "../middleware/auth.js";
import { listUserOsrmPrepareJobs } from "../repos/osrmPrepareJobs.js";
import {
  listOsrmEligibleCities,
  listOsrmReadyCities,
} from "../services/osrmReadyCities.js";
import {
  enqueueUserOsrmPrepare,
  getOsrmPrepareJobForUser,
  OsrmPrepareError,
} from "../services/osrmPrepare.js";

export async function registerCitiesRoutes(app: FastifyInstance): Promise<void> {
  app.get(
    "/api/cities/osrm-ready",
    {
      schema: {
        tags: ["cities"],
        summary: "Города с готовым пешим OSRM-графом на этом сервере",
        response: {
          200: {
            type: "object",
            properties: {
              cities: {
                type: "array",
                items: {
                  type: "object",
                  properties: {
                    slug: { type: "string" },
                    display_name: { type: "string" },
                  },
                  required: ["slug", "display_name"],
                },
              },
            },
            required: ["cities"],
          },
        },
      },
    },
    async () => ({ cities: listOsrmReadyCities() }),
  );

  app.get(
    "/api/cities/osrm-eligible",
    {
      schema: {
        tags: ["cities"],
        summary: "Города каталога: FO есть, OSRM ещё нет (self-serve)",
        response: {
          200: {
            type: "object",
            properties: {
              cities: {
                type: "array",
                items: {
                  type: "object",
                  properties: {
                    slug: { type: "string" },
                    display_name: { type: "string" },
                    federal_district: { type: "string" },
                  },
                  required: ["slug", "display_name", "federal_district"],
                },
              },
              quota_limit: { type: "integer" },
            },
            required: ["cities", "quota_limit"],
          },
        },
      },
    },
    async () => ({
      cities: listOsrmEligibleCities(),
      quota_limit: config.osrmPrepareQuotaPerUser,
    }),
  );
}

export async function registerOsrmPrepareRoutes(app: FastifyInstance): Promise<void> {
  app.post(
    "/api/osrm-prepares",
    {
      preHandler: requireAuth,
      schema: {
        tags: ["osrm"],
        summary: "Поставить подготовку OSRM в очередь",
        security: [...bearerSecurity],
        body: {
          type: "object",
          required: ["slug"],
          properties: { slug: { type: "string" } },
        },
      },
    },
    async (request, reply) => {
      const body = z.object({ slug: z.string().min(1) }).safeParse(request.body);
      if (!body.success) {
        return reply.code(400).send({ detail: "Укажите slug города" });
      }
      try {
        const result = await enqueueUserOsrmPrepare({
          user: request.user!,
          slug: body.data.slug,
        });
        return reply.code(result.joined ? 200 : 202).send({
          job: result.job,
          joined: Boolean(result.joined),
        });
      } catch (err) {
        if (err instanceof OsrmPrepareError) {
          return reply.code(err.statusCode).send({ detail: err.message });
        }
        throw err;
      }
    },
  );

  app.get(
    "/api/osrm-prepares",
    {
      preHandler: requireAuth,
      schema: {
        tags: ["osrm"],
        summary: "Мои задачи подготовки OSRM",
        security: [...bearerSecurity],
      },
    },
    async (request) => ({
      jobs: await listUserOsrmPrepareJobs(request.user!.id),
      quota_used: request.user!.osrm_prepare_quota_used ?? 0,
      quota_limit: config.osrmPrepareQuotaPerUser,
    }),
  );

  app.get(
    "/api/osrm-prepares/:id",
    {
      preHandler: requireAuth,
      schema: {
        tags: ["osrm"],
        summary: "Статус задачи подготовки OSRM",
        security: [...bearerSecurity],
      },
    },
    async (request, reply) => {
      const id = (request.params as { id: string }).id;
      try {
        const job = await getOsrmPrepareJobForUser(request.user!.id, id);
        return { job };
      } catch (err) {
        if (err instanceof OsrmPrepareError) {
          return reply.code(err.statusCode).send({ detail: err.message });
        }
        throw err;
      }
    },
  );
}
