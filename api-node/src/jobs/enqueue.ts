export const QUEUE_BUILD_ROUTES = "tourist:queue:build_routes";
export const QUEUE_CITY_FACT = "tourist:queue:city_fact";

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
