import { recordAuditEvent } from "../repos/audit.js";
import { touchUserLastSeen } from "../repos/users.js";

export async function recordUserRegister(
  userId: number,
  metadata?: Record<string, unknown>,
): Promise<void> {
  await recordAuditEvent({
    action: "user.register",
    entityType: "user",
    entityId: String(userId),
    userId,
    metadata,
  });
}

export async function recordUserLogin(
  userId: number,
  metadata?: Record<string, unknown>,
): Promise<void> {
  await recordAuditEvent({
    action: "user.login",
    entityType: "user",
    entityId: String(userId),
    userId,
    metadata,
  });
  await touchUserLastSeen(userId);
}
