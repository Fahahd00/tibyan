/**
 * Minimal, transparent SQL migration runner.
 *
 * - Applies db/migrations/NNNN_*.sql in lexical order, each in its own transaction.
 * - Records version + SHA-256 checksum in schema_migrations.
 * - Refuses to run if an already-applied migration file was modified.
 * - Uses a PostgreSQL advisory lock so concurrent runs (e.g. several containers) are safe.
 */
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import pg from "pg";
import { loadConfig, repoPaths } from "../config.js";

const LOCK_ID = 727_001;

export interface MigrationFile {
  version: string;
  name: string;
  sql: string;
  checksum: string;
}

export function readMigrations(dir: string): MigrationFile[] {
  return readdirSync(dir)
    .filter((f) => /^\d{4}_[a-z0-9_]+\.sql$/.test(f))
    .sort()
    .map((name) => {
      const sql = readFileSync(join(dir, name), "utf8");
      return {
        version: name.slice(0, 4),
        name,
        sql,
        checksum: createHash("sha256").update(sql).digest("hex"),
      };
    });
}

export async function migrate(
  databaseUrl: string,
  dir: string,
  log = console.log,
): Promise<string[]> {
  const client = new pg.Client({ connectionString: databaseUrl });
  await client.connect();
  const applied: string[] = [];
  try {
    await client.query("SELECT pg_advisory_lock($1)", [LOCK_ID]);
    await client.query(`
      CREATE TABLE IF NOT EXISTS schema_migrations (
        version     text PRIMARY KEY,
        name        text NOT NULL,
        checksum    text NOT NULL,
        applied_at  timestamptz NOT NULL DEFAULT now()
      )`);
    const { rows } = await client.query<{ version: string; checksum: string; name: string }>(
      "SELECT version, name, checksum FROM schema_migrations",
    );
    const done = new Map(rows.map((r) => [r.version, r]));

    for (const m of readMigrations(dir)) {
      const prev = done.get(m.version);
      if (prev) {
        if (prev.checksum !== m.checksum) {
          throw new Error(
            `Migration ${m.name} was modified after being applied (checksum mismatch). ` +
              "Create a new migration instead of editing an applied one.",
          );
        }
        continue;
      }
      log(`→ applying ${m.name}`);
      await client.query("BEGIN");
      try {
        await client.query(m.sql);
        await client.query(
          "INSERT INTO schema_migrations (version, name, checksum) VALUES ($1, $2, $3)",
          [m.version, m.name, m.checksum],
        );
        await client.query("COMMIT");
        applied.push(m.name);
      } catch (err) {
        await client.query("ROLLBACK");
        throw new Error(`Migration ${m.name} failed: ${(err as Error).message}`);
      }
    }
    log(
      applied.length
        ? `✓ applied ${applied.length} migration(s)`
        : "✓ database schema is up to date",
    );
    return applied;
  } finally {
    await client.query("SELECT pg_advisory_unlock($1)", [LOCK_ID]).catch(() => undefined);
    await client.end();
  }
}

const isMain = import.meta.url === pathToFileURL(process.argv[1] ?? "").href;
if (isMain) {
  const config = loadConfig();
  const dir = process.env.MIGRATIONS_DIR ?? repoPaths.migrations;
  migrate(config.DATABASE_URL, dir).catch((err: Error) => {
    console.error(`✗ ${err.message}`);
    process.exit(1);
  });
}
