import { createHash, randomUUID } from "node:crypto";
import type { RequestHandler } from "express";
import type { Db } from "../lib/db.js";
import { UUID_RE } from "../lib/db.js";

export const SESSION_COOKIE = "tibyan_sid";
const MAX_AGE_S = 60 * 60 * 24 * 30;

declare module "express-serve-static-core" {
  interface Request {
    sessionId?: string;
  }
}

function readCookie(header: string | undefined, name: string): string | undefined {
  if (!header) return undefined;
  for (const part of header.split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return decodeURIComponent(v.join("="));
  }
  return undefined;
}

/** Anonymous session: a random id in an HttpOnly cookie, recorded in `sessions`. No personal data. */
export function session(db: Db, secureCookies: boolean): RequestHandler {
  return async (req, res, next) => {
    let sid = readCookie(req.headers.cookie, SESSION_COOKIE);
    if (!sid || !UUID_RE.test(sid)) {
      sid = randomUUID();
      res.cookie(SESSION_COOKIE, sid, {
        httpOnly: true,
        sameSite: "lax",
        secure: secureCookies,
        maxAge: MAX_AGE_S * 1000,
        path: "/",
      });
    }
    req.sessionId = sid;
    const ua = req.headers["user-agent"];
    const uaHash = ua ? createHash("sha256").update(ua).digest("hex").slice(0, 16) : null;
    const locale = typeof req.body?.locale === "string" ? req.body.locale : null;
    await db.query(
      `INSERT INTO sessions (id, locale, user_agent_hash) VALUES ($1, $2, $3)
       ON CONFLICT (id) DO UPDATE SET last_seen_at = now(), locale = COALESCE(EXCLUDED.locale, sessions.locale)`,
      [sid, locale, uaHash],
    );
    next();
  };
}
