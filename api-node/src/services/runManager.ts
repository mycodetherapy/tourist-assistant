import { config } from "../config.js";
import { enqueueBuildRoutes } from "../jobs/enqueue.js";
import {
  acquireTripBuildLock,
  createGraphRun,
  failStaleGraphRuns,
  getGraphRun,
  hasActiveGraphRun,
  releaseTripBuildLock,
  updateGraphRun,
} from "../repos/graphRuns.js";
import { getTrip } from "../repos/trips.js";
import { recordAuditEvent } from "../repos/audit.js";
import { checkAndConsumeRunQuota } from "./quotas.js";

export async function startRun(tripId: number, scope: string): Promise<string> {
  const trip = await getTrip(tripId);
  if (!trip) {
    throw new Error(`Поездка #${tripId} не найдена`);
  }
  const userId = trip.user_id;
  await checkAndConsumeRunQuota(userId, scope);
  await recordAuditEvent({
    action: "graph_run.start",
    entityType: "trip",
    entityId: String(tripId),
    userId,
    metadata: { scope },
  });

  await failStaleGraphRuns(tripId, config.graphRunStaleSec);
  if (await hasActiveGraphRun(tripId)) {
    throw new Error("Для поездки уже выполняется сборка маршрута");
  }
  if (!(await acquireTripBuildLock(tripId))) {
    throw new Error("Для поездки уже выполняется сборка маршрута");
  }

  const cityFactStatus = scope === "full" ? "pending" : "skipped";
  const runId = await createGraphRun({
    userId,
    tripId,
    scope,
    cityFactStatus,
  });
  const payload = { trip_id: tripId, user_id: userId, scope };
  try {
    await enqueueBuildRoutes(runId, payload);
  } catch (err) {
    await releaseTripBuildLock(tripId);
    const message = err instanceof Error ? err.message : String(err);
    await updateGraphRun(runId, {
      status: "failed",
      error: message,
      finished_at: new Date(),
    });
    throw err;
  }
  return runId;
}

export async function getRunStatus(runId: string) {
  return getGraphRun(runId);
}

export async function hasActiveRunForTrip(tripId: number): Promise<boolean> {
  return hasActiveGraphRun(tripId);
}
