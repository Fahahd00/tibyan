import type { ErrorRequestHandler, RequestHandler } from "express";
import { ZodError } from "zod";

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export const notFound: RequestHandler = (_req, _res, next) => {
  next(new HttpError(404, "not_found", "Route not found"));
};

export const errorHandler: ErrorRequestHandler = (err, req, res, _next) => {
  const requestId = String(req.id ?? "");
  if (err instanceof ZodError) {
    res.status(400).json({
      error: {
        code: "invalid_request",
        message: err.issues.map((i) => `${i.path.join(".") || "body"}: ${i.message}`).join("; "),
        request_id: requestId,
      },
    });
    return;
  }
  if (err instanceof HttpError) {
    res
      .status(err.status)
      .json({ error: { code: err.code, message: err.message, request_id: requestId } });
    return;
  }
  if (err?.type === "entity.too.large") {
    res.status(413).json({
      error: {
        code: "payload_too_large",
        message: "Request body too large",
        request_id: requestId,
      },
    });
    return;
  }
  if (err?.type === "entity.parse.failed") {
    res.status(400).json({
      error: { code: "invalid_json", message: "Malformed JSON body", request_id: requestId },
    });
    return;
  }
  req.log?.error({ err }, "unhandled error");
  res.status(500).json({
    error: { code: "internal_error", message: "Internal server error", request_id: requestId },
  });
};
