import { useCallback, useRef, type TouchEvent } from "react";

const MIN_DISTANCE_PX = 56;
const FLICK_DISTANCE_PX = 28;
const FLICK_VELOCITY = 0.4;
const MAX_SLOPE = 0.7;
const AXIS_LOCK_PX = 10;

export type SwipeDirection = "left" | "right";

/**
 * Горизонтальный свайп без перехвата вертикального скролла.
 * Карта должна глушить touch-события (stopPropagation), иначе жест уйдёт в панораму.
 */
export function useHorizontalSwipe(
  enabled: boolean,
  onSwipe: (direction: SwipeDirection) => void,
) {
  const startRef = useRef<{ x: number; y: number; t: number } | null>(null);
  const axisRef = useRef<"h" | "v" | null>(null);

  const reset = () => {
    startRef.current = null;
    axisRef.current = null;
  };

  const onTouchStart = useCallback(
    (event: TouchEvent) => {
      if (!enabled || event.touches.length !== 1) {
        reset();
        return;
      }
      const touch = event.touches[0];
      startRef.current = { x: touch.clientX, y: touch.clientY, t: Date.now() };
      axisRef.current = null;
    },
    [enabled],
  );

  const onTouchMove = useCallback(
    (event: TouchEvent) => {
      if (!enabled || !startRef.current || event.touches.length !== 1) {
        return;
      }
      const touch = event.touches[0];
      const dx = touch.clientX - startRef.current.x;
      const dy = touch.clientY - startRef.current.y;
      if (axisRef.current || (Math.abs(dx) < AXIS_LOCK_PX && Math.abs(dy) < AXIS_LOCK_PX)) {
        return;
      }
      axisRef.current = Math.abs(dx) > Math.abs(dy) ? "h" : "v";
    },
    [enabled],
  );

  const onTouchEnd = useCallback(
    (event: TouchEvent) => {
      const start = startRef.current;
      const axis = axisRef.current;
      const touch = event.changedTouches[0];
      reset();
      if (!enabled || !start || axis === "v" || !touch) {
        return;
      }
      const dx = touch.clientX - start.x;
      const dy = touch.clientY - start.y;
      if (Math.abs(dx) < 8) {
        return;
      }
      if (Math.abs(dy) / Math.max(Math.abs(dx), 1) > MAX_SLOPE) {
        return;
      }
      const velocity = Math.abs(dx) / Math.max(Date.now() - start.t, 1);
      const isFlick = Math.abs(dx) >= FLICK_DISTANCE_PX && velocity >= FLICK_VELOCITY;
      if (Math.abs(dx) < MIN_DISTANCE_PX && !isFlick) {
        return;
      }
      onSwipe(dx < 0 ? "left" : "right");
    },
    [enabled, onSwipe],
  );

  const onTouchCancel = useCallback(() => {
    reset();
  }, []);

  return { onTouchStart, onTouchMove, onTouchEnd, onTouchCancel };
}

export function adjacentCaseId(
  caseIds: string[],
  current: string | undefined,
  direction: SwipeDirection,
): string | undefined {
  if (caseIds.length === 0) {
    return undefined;
  }
  const idx = caseIds.indexOf(current ?? caseIds[0]);
  const from = idx < 0 ? 0 : idx;
  const next = direction === "left" ? from + 1 : from - 1;
  return caseIds[next];
}
