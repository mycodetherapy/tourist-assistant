/**
 * Экспорт OpenAPI 3 из зарегистрированных маршрутов Fastify → docs/openapi.json.
 * Запуск: npm run export:openapi (из api-node) или python3 scripts/export_openapi.py
 */
import { writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

process.env.OPENAPI_UI ??= "0";
process.env.DATABASE_URL ??=
  "postgresql://openapi:openapi@127.0.0.1:5432/openapi_export";
process.env.JWT_SECRET ??= "openapi-export-dummy-jwt-secret-32chars";
process.env.SETTINGS_ENCRYPTION_KEY ??=
  "dGVzdC1vcGVuYXBpLWV4cG9ydC1rZXktMzJieXRzISE=";

const repoRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const output = path.join(repoRoot, "docs", "openapi.json");

const { buildApp } = await import("../src/index.js");

const app = await buildApp({ enableSwaggerUi: false });
await app.ready();

const spec = app.swagger();
writeFileSync(output, `${JSON.stringify(spec, null, 2)}\n`, "utf-8");
console.log(`OpenAPI exported: ${path.relative(repoRoot, output)}`);

await app.close();
