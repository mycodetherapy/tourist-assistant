import path from "node:path";
import { pathToFileURL } from "node:url";
import "./loadEnv.js";
import Fastify from "fastify";
import cors from "@fastify/cors";
import cookie from "@fastify/cookie";
import rateLimit from "@fastify/rate-limit";
import { config } from "./config.js";
import { closePool } from "./db/pool.js";
import { closeRedis } from "./db/redis.js";
import {
  registerAuthRoutes,
  registerProfileRoutes,
} from "./routes/auth.js";
import { registerRunsRoutes } from "./routes/runs.js";
import { registerTripsRoutes } from "./routes/trips.js";

export async function buildApp() {
  const app = Fastify({ logger: true });

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

  app.get("/health", async () => ({ status: "ok" }));
  app.get("/api/health", async () => ({ status: "ok" }));

  await registerAuthRoutes(app);
  await registerProfileRoutes(app);
  await registerTripsRoutes(app);
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
  const shutdown = async () => {
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
