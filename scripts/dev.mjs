#!/usr/bin/env node
// Starts web, api and ai in watch mode with prefixed, colour-coded output.
// Requires the database to be running (docker compose up -d db) and migrated.
import { spawn } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const procs = [
  {
    name: "ai ",
    color: 35,
    cmd: "node",
    args: [
      "scripts/py.mjs",
      "-m",
      "uvicorn",
      "tibyan_ai.main:app",
      "--reload",
      "--app-dir",
      "services/ai",
      "--port",
      process.env.AI_PORT ?? "8000",
    ],
  },
  { name: "api", color: 36, cmd: "npm", args: ["run", "dev", "-w", "@tibyan/api"] },
  { name: "web", color: 32, cmd: "npm", args: ["run", "dev", "-w", "@tibyan/web"] },
];

const children = procs.map(({ name, color, cmd, args }) => {
  const child = spawn(cmd, args, {
    cwd: root,
    env: process.env,
    shell: process.platform === "win32",
  });
  const prefix = `\x1b[${color}m[${name}]\x1b[0m `;
  const pipe = (stream, out) =>
    stream.on("data", (buf) =>
      buf
        .toString()
        .split("\n")
        .filter(Boolean)
        .forEach((line) => out.write(prefix + line + "\n")),
    );
  pipe(child.stdout, process.stdout);
  pipe(child.stderr, process.stderr);
  child.on("exit", (code) => {
    process.stdout.write(`${prefix}exited with code ${code}\n`);
    shutdown(code ?? 1);
  });
  return child;
});

let stopping = false;
function shutdown(code) {
  if (stopping) return;
  stopping = true;
  children.forEach((c) => c.kill("SIGTERM"));
  setTimeout(() => process.exit(code), 500);
}
process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));
