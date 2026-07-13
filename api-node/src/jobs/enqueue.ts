export const QUEUE_BUILD_ROUTES = "tourist:queue:build_routes";
export const QUEUE_CITY_FACT = "tourist:queue:city_fact";
export const QUEUE_POI_FACT = "tourist:queue:poi_fact";

export interface JsonJob {
  task: string;
  graph_run_id: string;
  payload: Record<string, unknown>;
}

export async function enqueueBuildRoutes(
  graphRunId: string,
  payload: Record<string, unknown>,
): Promise<void> {
  const { getRedis } = await import("../db/redis.js");
  const redis = await getRedis();
  const job: JsonJob = {
    task: "build_routes",
    graph_run_id: graphRunId,
    payload,
  };
  await redis.rPush(QUEUE_BUILD_ROUTES, JSON.stringify(job));
}

export async function enqueuePoiFact(
  jobId: string,
  payload: Record<string, unknown>,
): Promise<void> {
  const { getRedis } = await import("../db/redis.js");
  const redis = await getRedis();
  const job: JsonJob = {
    task: "poi_fact",
    graph_run_id: jobId,
    payload,
  };
  await redis.rPush(QUEUE_POI_FACT, JSON.stringify(job));
}

export async function enqueueCityFact(
  graphRunId: string,
  payload: Record<string, unknown>,
): Promise<void> {
  const { getRedis } = await import("../db/redis.js");
  const redis = await getRedis();
  const job: JsonJob = {
    task: "city_fact",
    graph_run_id: graphRunId,
    payload,
  };
  await redis.rPush(QUEUE_CITY_FACT, JSON.stringify(job));
}
