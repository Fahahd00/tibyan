import { pino } from "pino";
import { createApp } from "./app.js";
import { loadConfig } from "./config.js";
import { createAiClient } from "./lib/aiClient.js";
import { closePool, getPool } from "./db/pool.js";

const config = loadConfig();
const logger = pino({ level: config.LOG_LEVEL, base: { service: "tibyan-api" } });
const pool = getPool(config.DATABASE_URL);
const ai = createAiClient(config.AI_SERVICE_URL, config.INTERNAL_API_TOKEN, config.AI_TIMEOUT_MS);
const app = createApp({ config, db: pool, ai, logger });

const server = app.listen(config.API_PORT, () => {
  logger.info({ port: config.API_PORT, ai: config.AI_SERVICE_URL }, "Tibyan API listening");
});

function shutdown(signal: string) {
  logger.info({ signal }, "shutting down");
  server.close(() => {
    void closePool().finally(() => process.exit(0));
  });
  setTimeout(() => process.exit(1), 10_000).unref();
}
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
