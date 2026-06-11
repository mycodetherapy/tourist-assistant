/** Выбор маршрута по голосам на вкладке «Маршруты». */

import type { TripRouteCase } from "../api/routeTypes";
import type { ItemVote, ProgramItem } from "../api/types";

const CASE_ORDER: Record<string, number> = {
  A: 0,
  B: 1,
  C: 2,
  "N-A": 10,
  "N-B": 11,
  "N-C": 12,
};

function caseSortKey(caseId: string): number {
  return CASE_ORDER[caseId] ?? 50;
}

/** Маршрут с 👍; при равенстве — A раньше B; без голосов — первый по порядку case_id. */
export function pickPreferredCaseId(
  cases: TripRouteCase[],
  routeItems: ProgramItem[],
): string | undefined {
  if (cases.length === 0) {
    return undefined;
  }
  const voteByCaseId = new Map<string, ItemVote | null>();
  for (const item of routeItems) {
    const routeCase = cases[item.index];
    if (routeCase) {
      voteByCaseId.set(String(routeCase.case_id), item.vote);
    }
  }
  for (const routeCase of cases) {
    if (!voteByCaseId.has(String(routeCase.case_id))) {
      voteByCaseId.set(String(routeCase.case_id), null);
    }
  }
  const liked = cases
    .map((c) => String(c.case_id))
    .filter((id) => voteByCaseId.get(id) === 1);
  if (liked.length > 0) {
    return liked.sort((a, b) => caseSortKey(a) - caseSortKey(b))[0];
  }
  return [...cases]
    .map((c) => String(c.case_id))
    .sort((a, b) => caseSortKey(a) - caseSortKey(b))[0];
}
