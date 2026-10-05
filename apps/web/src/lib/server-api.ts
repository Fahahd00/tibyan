import { connection } from "next/server";

/** Server-side reads from the API gateway (request time, never at build time). */
const base = process.env.API_INTERNAL_URL ?? "http://localhost:4000";

export async function serverGet<T>(path: string): Promise<T | null> {
  await connection();
  const res = await fetch(`${base}${path}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${path} responded ${res.status}`);
  return (await res.json()) as T;
}
