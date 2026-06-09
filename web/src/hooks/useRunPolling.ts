import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { fetchRun } from "../api/trips";

export function useRunPolling(runId: string | null) {
  return useQuery({
    queryKey: ["runs", runId],
    queryFn: () => fetchRun(runId!),
    enabled: !!runId,
    retry: (failureCount, error) => {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return false;
      }
      return failureCount < 2;
    },
    refetchInterval: (query) => {
      if (query.state.status === "error") {
        return false;
      }
      const status = query.state.data?.status;
      if (status === "queued" || status === "running") {
        return 2000;
      }
      return false;
    },
  });
}
