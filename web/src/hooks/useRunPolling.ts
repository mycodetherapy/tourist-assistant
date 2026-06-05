import { useQuery } from "@tanstack/react-query";
import { fetchRun } from "../api/trips";

export function useRunPolling(runId: string | null) {
  return useQuery({
    queryKey: ["runs", runId],
    queryFn: () => fetchRun(runId!),
    enabled: !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "queued" || status === "running") return 2000;
      return false;
    },
  });
}
