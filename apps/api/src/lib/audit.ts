import { createHash } from "node:crypto";
import type { Request } from "express";
import type { Db } from "./db.js";

export function hashIp(ip: string | undefined, salt: string): string | null {
  if (!ip) return null;
  return createHash("sha256").update(`${salt}:${ip}`).digest("hex").slice(0, 32);
}

export async function audit(
  db: Db,
  req: Request,
  salt: string,
  entry: {
    actor: string;
    action: string;
    entityType?: string;
    entityId?: string;
    details?: Record<string, unknown>;
  },
): Promise<void> {
  try {
    await db.query(
      `INSERT INTO audit_logs (actor, action, entity_type, entity_id, request_id, ip_hash, details)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        entry.actor,
        entry.action,
        entry.entityType ?? null,
        entry.entityId ?? null,
        String(req.id ?? ""),
        hashIp(req.ip, salt),
        JSON.stringify(entry.details ?? {}),
      ],
    );
  } catch (err) {
    // Auditing must never break the user-facing request; the failure itself is logged.
    req.log?.error({ err }, "failed to write audit log");
  }
}
