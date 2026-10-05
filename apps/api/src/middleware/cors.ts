import type { RequestHandler } from "express";

/** Allow-list CORS for clients that call the API directly (the web app uses a same-origin proxy). */
export function cors(origins: string[]): RequestHandler {
  const allowed = new Set(origins.map((o) => o.trim()).filter(Boolean));
  return (req, res, next) => {
    const origin = req.headers.origin;
    if (origin && allowed.has(origin)) {
      res.setHeader("Access-Control-Allow-Origin", origin);
      res.setHeader("Access-Control-Allow-Credentials", "true");
      res.setHeader("Vary", "Origin");
      res.setHeader("Access-Control-Allow-Headers", "content-type, authorization, x-request-id");
      res.setHeader("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS");
    }
    if (req.method === "OPTIONS") {
      res.status(204).end();
      return;
    }
    next();
  };
}
