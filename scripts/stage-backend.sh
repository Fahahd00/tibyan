#!/bin/sh
# Assembles the backend Space folder (the build context of deploy/backend/Dockerfile) in $1, and the corpus dump in
# $1.dump. The dump holds the fatwa texts, so it goes to a private dataset, never into the public Space.
# Run from the repository root with the local stack up.
set -e
out=${1:?usage: scripts/stage-backend.sh <out-dir>}
rm -rf "$out" && mkdir -p "$out"
tar --exclude=node_modules --exclude=dist --exclude=__pycache__ --exclude='data/corpus/*/*' -cf - \
  package.json package-lock.json tsconfig.base.json packages/contracts apps/api apps/web/package.json \
  services/ai/pyproject.toml services/ai/tibyan_ai data deploy/backend/start.sh | tar -xf - -C "$out"
cp deploy/backend/Dockerfile deploy/backend/README.md "$out/"
# Corpus and schema only: no sessions, questions or logs from local runs
docker compose exec -T db pg_dump -U tibyan -d tibyan -Fc --no-owner --no-privileges \
  --exclude-table-data=sessions --exclude-table-data=questions --exclude-table-data=answers \
  --exclude-table-data=retrievals --exclude-table-data=claims --exclude-table-data=audit_logs \
  --exclude-table-data=llm_usage >"$out.dump"
du -sh "$out" "$out.dump"
