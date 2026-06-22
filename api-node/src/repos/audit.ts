import { query } from "../db/pool.js";

export async function recordAuditEvent(params: {
  action: string;
  entityType: string;
  entityId: string;
  userId?: number;
  metadata?: Record<string, unknown>;
}): Promise<void> {
  await query(
    `INSERT INTO audit_events (user_id, action, entity_type, entity_id, metadata_json, created_at)
     VALUES ($1, $2, $3, $4, $5::jsonb, NOW())`,
    [
      params.userId ?? null,
      params.action,
      params.entityType,
      params.entityId,
      params.metadata ? JSON.stringify(params.metadata) : null,
    ],
  );
}
