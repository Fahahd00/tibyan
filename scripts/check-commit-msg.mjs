#!/usr/bin/env node
// Enforces Conventional Commits on the first line of a commit message.
import { readFileSync } from "node:fs";

const file = process.argv[2];
const header = readFileSync(file, "utf8").split("\n")[0].trim();
const pattern =
  /^(feat|fix|refactor|docs|test|chore|perf|ci|build|style|revert)(\([a-z0-9-]+\))?!?: .{3,}$/;

if (header.startsWith("Merge ") || header.startsWith("Revert ") || pattern.test(header))
  process.exit(0);

console.error(`\n✖ Commit message does not follow Conventional Commits:\n\n    ${header}\n`);
console.error("  Expected: <type>(optional-scope): <summary>");
console.error("  Types:    feat, fix, refactor, docs, test, chore, perf, ci, build, style, revert");
console.error("  Example:  feat(rag): add hybrid retrieval\n");
process.exit(1);
