import path from "node:path";
import { fileURLToPath } from "node:url";
import { config as loadDotenv } from "dotenv";

const apiNodeRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const repoRoot = path.resolve(apiNodeRoot, "..");

/** Корневой .env репозитория (как у Python API и worker). */
loadDotenv({ path: path.join(repoRoot, ".env") });
/** Локальные переопределения api-node/.env */
loadDotenv({ path: path.join(apiNodeRoot, ".env"), override: true });

export { apiNodeRoot, repoRoot };
