#!/usr/bin/env node
// Creates services/ai/.venv and installs the AI service with dev extras.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const aiDir = join(root, "services", "ai");
const isWin = process.platform === "win32";
const venvPython = join(aiDir, ".venv", isWin ? "Scripts/python.exe" : "bin/python");

function run(cmd, args) {
  console.log(`$ ${cmd} ${args.join(" ")}`);
  const r = spawnSync(cmd, args, { cwd: aiDir, stdio: "inherit" });
  if (r.status !== 0) process.exit(r.status ?? 1);
}

if (!existsSync(venvPython)) run(isWin ? "python" : "python3", ["-m", "venv", ".venv"]);
run(venvPython, ["-m", "pip", "install", "--upgrade", "pip"]);
run(venvPython, ["-m", "pip", "install", "-e", ".[dev,openai]"]);
console.log("AI service environment ready.");
