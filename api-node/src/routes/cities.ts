import type { FastifyInstance } from "fastify";
import { listOsrmReadyCities } from "../services/osrmReadyCities.js";

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
}
