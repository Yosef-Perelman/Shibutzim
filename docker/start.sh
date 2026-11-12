#!/bin/sh
# Container entry point: bring the schema up to date, then serve. Alembic takes a lock, so two
# instances starting together cannot apply a migration twice (plan 005, open question 8).
set -eu

cd /app/server
alembic upgrade head
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8080}" \
  --proxy-headers \
  --forwarded-allow-ips='*'
