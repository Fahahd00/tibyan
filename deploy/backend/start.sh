#!/bin/sh
# PostgreSQL and the AI service listen on localhost only; the API is the public port (7860).
# The fatwa texts are not in the image (they belong to their publishers): on first start the indexed corpus is
# restored from a private dataset, read with a secret. Questions asked on the site reset when the Space restarts.
set -e
PG=/usr/lib/postgresql/16/bin
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  $PG/initdb -D "$PGDATA" -U tibyan --auth=trust -E UTF8 --locale=C.UTF-8 >/dev/null
  curl -fsSL -H "Authorization: Bearer $CORPUS_TOKEN" -o /tmp/tibyan.dump \
    "https://huggingface.co/datasets/$CORPUS_REPO/resolve/main/tibyan.dump"
  $PG/pg_ctl -D "$PGDATA" -o "-c listen_addresses='' -k /tmp" -w start
  $PG/createdb -h /tmp -U tibyan tibyan
  $PG/pg_restore -h /tmp -U tibyan -d tibyan --no-owner --no-privileges /tmp/tibyan.dump
  $PG/pg_ctl -D "$PGDATA" -m fast -w stop
  rm -f /tmp/tibyan.dump
fi
$PG/pg_ctl -D "$PGDATA" -o "-c listen_addresses=127.0.0.1 -k /tmp" -l "$HOME/postgres.log" -w start
uvicorn tibyan_ai.main:app --host 127.0.0.1 --port 8000 &
until curl -sf http://127.0.0.1:8000/health >/dev/null; do sleep 1; done
exec node apps/api/dist/server.js
