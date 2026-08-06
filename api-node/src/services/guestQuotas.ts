import type { GuestSessionRow } from "../repos/guestSessions.js";

export const GUEST_FULL_RUN_LIMIT = 1;
export const GUEST_PARTIAL_RUN_LIMIT = 1;

export class GuestRegisterRequiredError extends Error {
  readonly code = "register_required" as const;
  constructor(message: string) {
    super(message);
  }
}

export function guestSessionExpired(session: GuestSessionRow): boolean {
  return new Date(session.expires_at).getTime() <= Date.now();
}

export function assertGuestCanCreateTrip(session: GuestSessionRow): void {
  if (session.trip_id != null) {
    throw new GuestRegisterRequiredError(
      "Зарегистрируйтесь, чтобы собрать маршрут для другого города или сохранить прогулку",
    );
  }
  if (session.full_runs_used >= GUEST_FULL_RUN_LIMIT) {
    throw new GuestRegisterRequiredError(
      "Лимит пробной сборки исчерпан — зарегистрируйтесь для продолжения",
    );
  }
}

export function assertGuestCanStartRun(
  session: GuestSessionRow,
  scope: string,
): void {
  if (scope === "full") {
    if (session.full_runs_used >= GUEST_FULL_RUN_LIMIT) {
      throw new GuestRegisterRequiredError(
        "Глубокий пересбор доступен после регистрации",
      );
    }
    return;
  }
  if (scope === "routes") {
    if (session.partial_runs_used >= GUEST_PARTIAL_RUN_LIMIT) {
      throw new GuestRegisterRequiredError(
        "Пересбор маршрутов доступен после регистрации",
      );
    }
    return;
  }
  throw new GuestRegisterRequiredError("Это действие доступно после регистрации");
}
