import { randomUUID } from "node:crypto";
import express from "express";
import helmet from "helmet";
import { pinoHttp } from "pino-http";
import type { Logger } from "pino";
import type { Config } from "./config.js";
import type { AiClient } from "./lib/aiClient.js";
import type { Db } from "./lib/db.js";
import { errorHandler, notFound } from "./lib/errors.js";
import { adminAuth } from "./middleware/admin.js";
import { cors } from "./middleware/cors.js";
import { session } from "./middleware/session.js";
import { adminRouter } from "./routes/admin.js";
import { answersRouter } from "./routes/answers.js";
import { healthRouter } from "./routes/health.js";
import { questionsRouter } from "./routes/questions.js";
import { sourcesRouter } from "./routes/sources.js";
import { voiceRouter } from "./routes/voice.js";

export interface AppDeps {
  config: Config;
  db: Db;
  ai: AiClient;
  logger: Logger;
  version?: string;
}

export function createApp({ config, db, ai, logger, version = "1.1.0" }: AppDeps): express.Express {
  const app = express();
  app.disable("x-powered-by");
  // One trusted hop: the Next.js same-origin proxy (or a load balancer) in front of the API.
  app.set("trust proxy", 1);

  app.use(
    pinoHttp({
      logger,
      genReqId: (req, res) => {
        const incoming = req.headers["x-request-id"];
        const id = typeof incoming === "string" && incoming.length <= 64 ? incoming : randomUUID();
        res.setHeader("x-request-id", id);
        return id;
      },
      autoLogging: { ignore: (req) => req.url === "/api/health" },
    }),
  );
  // The web app may be served from another origin (e.g. Netlify) and play answer audio from here.
  app.use(helmet({ crossOriginResourcePolicy: { policy: "cross-origin" } }));
  app.use(cors(config.CORS_ORIGINS.split(",")));
  app.use(express.json({ limit: "32kb" }));

  const secure = config.APP_ENV === "production";
  const api = express.Router();
  api.use(healthRouter(db, ai, version));
  api.use(sourcesRouter(db));
  api.use(answersRouter(db));
  api.use(
    session(db, secure),
    questionsRouter({
      db,
      ai,
      perMinute: config.RATE_LIMIT_PER_MINUTE,
      ipSalt: config.IP_HASH_SALT,
    }),
  );
  api.use(voiceRouter(ai, config.RATE_LIMIT_PER_MINUTE));
  api.use(
    "/admin",
    adminAuth(config.ADMIN_TOKEN),
    adminRouter({ db, ai, ipSalt: config.IP_HASH_SALT }),
  );
  app.use("/api", api);

  app.use(notFound);
  app.use(errorHandler);
  return app;
}
