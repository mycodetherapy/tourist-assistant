import path from "node:path";
import { pathToFileURL } from "node:url";
import "./loadEnv.js";
import Fastify, { type FastifyError, type FastifyInstance } from "fastify";
import cors from "@fastify/cors";
import cookie from "@fastify/cookie";
import rateLimit from "@fastify/rate-limit";
import { config } from "./config.js";
import { closePool } from "./db/pool.js";
import { closeRedis } from "./db/redis.js";
import { startGuestCleanupScheduler, stopGuestCleanupScheduler } from "./services/guestCleanup.js";
import {
  registerAuthRoutes,
  registerProfileRoutes,
} from "./routes/auth.js";
import { registerRunsRoutes } from "./routes/runs.js";
import { registerTripsRoutes } from "./routes/trips.js";
import { registerGuestRoutes } from "./routes/guest.js";
import { registerCityRequestRoutes } from "./routes/cityRequests.js";
import { registerCitiesRoutes } from "./routes/cities.js";
import { registerSwagger } from "./plugins/swagger.js";

export type BuildAppOptions = {
  /** Swagger UI на /docs (по умолчанию включён). */
  enableSwaggerUi?: boolean;
};

/** Ошибки JSON Schema → 400 с `{ detail }`, иначе Fastify падает с 500 (FST_ERR_FAILED_ERROR_SERIALIZATION). */
function registerErrorHandler(app: FastifyInstance): void {
  app.setErrorHandler((error: FastifyError, request, reply) => {
    if (error.validation) {
      return reply.code(400).send({ detail: "Некорректные данные" });
    }
    if (
      error.code === "FST_ERR_RESPONSE_SERIALIZATION" ||
      error.code === "FST_ERR_FAILED_ERROR_SERIALIZATION"
    ) {
      request.log.error({ err: error }, "Response serialization failed");
      return reply.code(500).send({ detail: "Внутренняя ошибка сервера" });
    }
    const status = error.statusCode ?? 500;
    if (status >= 500) {
      request.log.error(error);
      return reply.code(500).send({ detail: "Внутренняя ошибка сервера" });
    }
    const detail =
      typeof error.message === "string" && error.message
        ? error.message
        : "Ошибка запроса";
    return reply.code(status).send({ detail });
  });
}

export async function buildApp(options: BuildAppOptions = {}) {
  const app = Fastify({ logger: true });
  registerErrorHandler(app);

  await app.register(cors, {
    origin: config.corsOrigins.length ? config.corsOrigins : true,
    credentials: true,
  });

  await app.register(cookie, {
    secret: config.jwtSecret(),
    hook: "onRequest",
  });

  await app.register(rateLimit, {
    max: 120,
    timeWindow: "1 minute",
  });

  await registerSwagger(app, { enableUi: options.enableSwaggerUi });

  app.get(
    "/health",
    {
      schema: {
        tags: ["health"],
        response: { 200: { $ref: "HealthResponse#" } },
      },
    },
    async () => ({ status: "ok" as const }),
  );
  app.get(
    "/api/health",
    {
      schema: {
        tags: ["health"],
        response: { 200: { $ref: "HealthResponse#" } },
      },
    },
    async () => ({ status: "ok" as const }),
  );

  await registerAuthRoutes(app);
  await registerProfileRoutes(app);
  await registerTripsRoutes(app);
  await registerGuestRoutes(app);
  await registerCityRequestRoutes(app);
  await registerCitiesRoutes(app);
  await registerRunsRoutes(app);

  return app;
}

async function main() {
  if (!(process.env.DATABASE_URL ?? "").trim()) {
    console.error(
      "DATABASE_URL не задан. Добавьте в корневой .env, например:\n" +
        "  DATABASE_URL=postgresql+psycopg://tourist:tourist@localhost:5433/tourist",
    );
    process.exit(1);
  }
  const app = await buildApp();
  startGuestCleanupScheduler((msg) => app.log.info(msg));
  const shutdown = async () => {
    stopGuestCleanupScheduler();
    await app.close();
    await closeRedis();
    await closePool();
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
  await app.listen({ port: config.port, host: "0.0.0.0" });
}

const isDirectRun =
  Boolean(process.argv[1]) &&
  import.meta.url === pathToFileURL(path.resolve(process.argv[1]!)).href;

if (isDirectRun) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
