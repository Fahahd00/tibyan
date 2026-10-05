#!/usr/bin/env node
// Runs Python from the AI service virtualenv (services/ai/.venv) when present,
// falling back to python3 on PATH. Always runs from the repository root.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const isWin = process.platform === "win32";
const venvPython = join(
  root,
  "services",
  "ai",
  ".venv",
  isWin ? "Scripts/python.exe" : "bin/python",
);
const python = existsSync(venvPython) ? venvPython : isWin ? "python" : "python3";

const result = spawnSync(python, process.argv.slice(2), {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, PYTHONPATH: join(root, "services", "ai") },
});
if (result.error) {
  console.error(`Failed to run ${python}: ${result.error.message}`);
  console.error("Run `npm run ai:setup` first.");
  process.exit(1);
}
process.exit(result.status ?? 1);
