import { useCallback, useEffect, useRef, useState } from "react";
import { fetchPoiFact, startPoiFact, type PoiFactResponse } from "../api/poiFacts";
import { guestFetchPoiFact, guestStartPoiFact } from "../api/guest";

const POLL_INTERVAL_MS = 1500;
const MAX_POLL_ATTEMPTS = 24;

export interface PoiFactTarget {
  poiId: string;
  name: string;
}

export function usePoiFact(tripId: number, options?: { guest?: boolean }) {
  const guest = options?.guest ?? false;
  const startFact = guest ? guestStartPoiFact : startPoiFact;
  const fetchFact = guest ? guestFetchPoiFact : fetchPoiFact;
  const [target, setTarget] = useState<PoiFactTarget | null>(null);
  const [data, setData] = useState<PoiFactResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollAttempts = useRef(0);

  const clearPoll = useCallback(() => {
    if (pollTimer.current) {
      clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
    pollAttempts.current = 0;
  }, []);

  const close = useCallback(() => {
    clearPoll();
    setTarget(null);
    setData(null);
    setLoading(false);
    setError(null);
  }, [clearPoll]);

  const poll = useCallback(
    async (cacheKey: string) => {
      try {
        const response = await fetchFact(tripId, cacheKey);
        setData(response);
        if (response.status === "ready") {
          setLoading(false);
          clearPoll();
          return;
        }
        if (response.status === "failed") {
          setLoading(false);
          setError(response.error || "Не удалось загрузить справку");
          clearPoll();
          return;
        }
        pollAttempts.current += 1;
        if (pollAttempts.current >= MAX_POLL_ATTEMPTS) {
          setLoading(false);
          setError("Превышено время ожидания. Попробуйте позже.");
          clearPoll();
          return;
        }
        pollTimer.current = setTimeout(() => {
          void poll(cacheKey);
        }, POLL_INTERVAL_MS);
      } catch (err) {
        setLoading(false);
        setError(err instanceof Error ? err.message : "Ошибка загрузки");
        clearPoll();
      }
    },
    [tripId, clearPoll, fetchFact],
  );

  const open = useCallback(
    async (next: PoiFactTarget) => {
      clearPoll();
      setTarget(next);
      setData(null);
      setError(null);
      setLoading(true);
      try {
        const response = await startFact(tripId, {
          poi_id: next.poiId || null,
          name: next.name,
        });
        setData(response);
        if (response.status === "ready" && response.text) {
          setLoading(false);
          return;
        }
        if (response.status === "failed") {
          setLoading(false);
          setError(response.error || "Не удалось загрузить справку");
          return;
        }
        pollAttempts.current = 0;
        pollTimer.current = setTimeout(() => {
          void poll(response.cache_key);
        }, POLL_INTERVAL_MS);
      } catch (err) {
        setLoading(false);
        setError(err instanceof Error ? err.message : "Ошибка запуска");
      }
    },
    [tripId, poll, clearPoll, startFact],
  );

  useEffect(() => () => clearPoll(), [clearPoll]);

  return {
    target,
    data,
    loading,
    error,
    open,
    close,
    isOpen: target !== null,
  };
}
