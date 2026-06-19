import { useQuery } from "@tanstack/react-query";
import { fetchProgram, fetchTrip } from "../api/trips";

export function useTrip(tripId: number) {
  return useQuery({
    queryKey: ["trips", tripId],
    queryFn: () => fetchTrip(tripId),
    enabled: tripId > 0,
  });
}

export function useTripProgram(tripId: number, enabled = true) {
  return useQuery({
    queryKey: ["trips", tripId, "program"],
    queryFn: () => fetchProgram(tripId),
    enabled: tripId > 0 && enabled,
    retry: false,
    staleTime: 0,
    refetchOnMount: "always",
    refetchInterval: (query) => {
      if (query.state.status === "error") {
        return false;
      }
      const status = query.state.data?.city_fact_status;
      if (status === "pending") {
        return 2500;
      }
      return false;
    },
  });
}
