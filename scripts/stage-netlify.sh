#!/bin/sh
# Assembles the folder uploaded to Netlify in $1: the web app and what it builds from, nothing else (no .env).
set -e
out=${1:?usage: scripts/stage-netlify.sh <out-dir>}
rm -rf "$out" && mkdir -p "$out"
tar --exclude=node_modules --exclude=.next --exclude=test-results --exclude=playwright-report --exclude=tsconfig.tsbuildinfo -cf - \
  package.json package-lock.json tsconfig.base.json packages/contracts apps/web apps/api/package.json |
  tar -xf - -C "$out"
cp deploy/netlify/netlify.toml "$out/"
du -sh "$out"
