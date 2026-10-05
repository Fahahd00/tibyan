import { timingSafeEqual } from "node:crypto";
import type { RequestHandler } from "express";
import { HttpError } from "../lib/errors.js";

/** Bearer-token guard for /api/admin. Admin is disabled entirely when ADMIN_TOKEN is empty. */
export function adminAuth(token: string): RequestHandler {
  const expected = Buffer.from(token);
  return (req, _res, next) => {
    if (!token)
      return next(new HttpError(503, "admin_disabled", "Admin is disabled (ADMIN_TOKEN not set)"));
    const header = req.headers.authorization ?? "";
    const provided = Buffer.from(header.startsWith("Bearer ") ? header.slice(7) : "");
    if (provided.length !== expected.length || !timingSafeEqual(provided, expected)) {
      return next(new HttpError(401, "unauthorized", "Invalid admin token"));
    }
    next();
  };
}
