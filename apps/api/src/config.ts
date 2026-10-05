import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";

// In local development, load the repo-root .env (Docker passes env vars directly).
const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const envFile = join(repoRoot, ".env");
if (existsSync(envFile) && typeof process.loadEnvFile === "function") {
  try {
    process.loadEnvFile(envFile);
  } catch {
    // ignore malformed .env; zod validation below reports what is missing
  }
}

const schema = z.object({
  APP_ENV: z.enum(["development", "production", "test"]).default("development"),
  LOG_LEVEL: z.string().default("info"),
  API_PORT: z.coerce.number().int().positive().default(4000),
  DATABASE_URL: z.string().min(1),
  AI_SERVICE_URL: z.string().url().default("http://localhost:8000"),
  INTERNAL_API_TOKEN: z.string().default(""),
  ADMIN_TOKEN: z.string().default(""),
  CORS_ORIGINS: z.string().default("http://localhost:3000"),
  AI_TIMEOUT_MS: z.coerce.number().int().positive().default(180_000),
  RATE_LIMIT_PER_MINUTE: z.coerce.number().int().positive().default(30),
  IP_HASH_SALT: z.string().default("tibyan-local-salt"),
});

export type Config = z.infer<typeof schema>;

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const parsed = schema.safeParse(env);
  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((i) => `  - ${i.path.join(".")}: ${i.message}`)
      .join("\n");
    throw new Error(`Invalid environment configuration:\n${issues}\nSee .env.example.`);
  }
  if (parsed.data.APP_ENV === "production" && !parsed.data.INTERNAL_API_TOKEN) {
    throw new Error("INTERNAL_API_TOKEN is required when APP_ENV=production");
  }
  return parsed.data;
}

export const repoPaths = {
  root: repoRoot,
  migrations: join(repoRoot, "db", "migrations"),
};
