import { config } from "../config.js";
import { AuthError, getUserLlmMode } from "./auth.js";
import { assertEmailVerified, requireVerifiedForOsrm } from "./emailVerify.js";
import { getOsrmPrepareLock } from "./osrmPrepareAccess.js";
import { enqueuePrepareOsrm } from "../jobs/enqueue.js";
import {
  createOsrmPrepareJob,
  findActiveOsrmPrepareJob,
  getOsrmPrepareJob,
  type OsrmPrepareJob,
} from "../repos/osrmPrepareJobs.js";
import {
  getUserSettings,
  tryReserveOsrmPrepareQuota,
  refundOsrmPrepareQuota,
  type User,
} from "../repos/users.js";
import {
  assertDiskHasFreeGb,
  countOsrmReadyCities,
  getCityPackEntry,
  isOsrmGraphReady,
  listOsrmEligibleCities,
  resolveCitiesRoot,
} from "./osrmReadyCities.js";

export class OsrmPrepareError extends AuthError {}

async function checkEnqueueRateLimit(userId: number): Promise<void> {
  const { getRedis } = await import("../db/redis.js");
  const redis = await getRedis();
  const slot = Math.floor(Date.now() / 3_600_000);
  const key = `osrm_prepare_enqueue:${userId}:${slot}`;
  const n = await redis.incr(key);
  if (n === 1) {
    await redis.expire(key, 3600);
  }
  if (n > config.osrmPrepareEnqueuePerHour) {
    await redis.decr(key);
    throw new OsrmPrepareError(
      "Слишком много запросов на подготовку — попробуйте позже",
      429,
    );
  }
}

export async function enqueueUserOsrmPrepare(params: {
  user: User;
  slug: string;
}): Promise<{ job: OsrmPrepareJob; already_ready?: boolean; joined?: boolean }> {
  const slug = params.slug.trim().toLowerCase();
  if (!slug) {
    throw new OsrmPrepareError("Укажите город", 400);
  }

  if (requireVerifiedForOsrm()) {
    assertEmailVerified(params.user);
  }

  const llmMode = await getUserLlmMode(params.user.id);
  const settings = await getUserSettings(params.user.id);
  const prepareLock = getOsrmPrepareLock(
    llmMode,
    Boolean(settings?.llm_api_key_enc),
  );
  if (prepareLock) {
    throw new OsrmPrepareError(prepareLock.message, 403);
  }

  const entry = getCityPackEntry(slug);
  if (!entry) {
    throw new OsrmPrepareError(
      "Город вне каталога. Оставьте заявку через форму «город не найден».",
      400,
    );
  }

  if (isOsrmGraphReady(resolveCitiesRoot(), slug)) {
    throw new OsrmPrepareError("Граф этого города уже готов", 409);
  }

  const eligible = listOsrmEligibleCities();
  if (!eligible.some((c) => c.slug === slug)) {
    throw new OsrmPrepareError(
      "Для этого города нет скачанного региона (FO) на сервере",
      400,
    );
  }

  try {
    assertDiskHasFreeGb(config.osrmPrepareMinFreeGb);
  } catch (err) {
    throw new OsrmPrepareError(
      err instanceof Error ? err.message : "Недостаточно места на диске",
      507,
    );
  }

  if (countOsrmReadyCities() >= config.osrmPrepareMaxCities) {
    throw new OsrmPrepareError(
      "Достигнут лимит городов с OSRM на сервере",
      503,
    );
  }

  const active = await findActiveOsrmPrepareJob(slug);
  if (active) {
    return { job: active, joined: true };
  }

  await checkEnqueueRateLimit(params.user.id);

  const reserved = await tryReserveOsrmPrepareQuota(
    params.user.id,
    config.osrmPrepareQuotaPerUser,
  );
  if (!reserved) {
    throw new OsrmPrepareError(
      `Лимит: не больше ${config.osrmPrepareQuotaPerUser} новых городов`,
      403,
    );
  }

  try {
    const job = await createOsrmPrepareJob({
      userId: params.user.id,
      slug,
      countsAgainstQuota: true,
    });
    await enqueuePrepareOsrm(job.id, {
      job_id: job.id,
      user_id: params.user.id,
      slug,
      display_name: entry.display_name,
      federal_district: entry.federal_district,
    });
    return { job };
  } catch (err) {
    await refundOsrmPrepareQuota(params.user.id);
    throw err;
  }
}

export async function getOsrmPrepareJobForUser(
  userId: number,
  jobId: string,
): Promise<OsrmPrepareJob> {
  const job = await getOsrmPrepareJob(jobId);
  if (!job) {
    throw new OsrmPrepareError("Задача не найдена", 404);
  }
  // Разрешаем смотреть чужой active job того же slug (joined)
  if (job.user_id !== userId) {
    const mineActive = await findActiveOsrmPrepareJob(job.slug);
    if (!mineActive || mineActive.id !== job.id) {
      throw new OsrmPrepareError("Задача не найдена", 404);
    }
  }
  return job;
}
