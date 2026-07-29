import path from "node:path";
import { fileURLToPath } from "node:url";
import { config as loadDotenv } from "dotenv";

const apiNodeRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const repoRoot = path.resolve(apiNodeRoot, "..");

/** Корневой .env репозитория (как у Python API и worker). Не override — Docker env_file важнее. */
loadDotenv({ path: path.join(repoRoot, ".env"), override: false });
/** Локальные переопределения api-node/.env (только dev). */
loadDotenv({ path: path.join(apiNodeRoot, ".env"), override: false });

export { apiNodeRoot, repoRoot };
