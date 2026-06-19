#!/bin/sh
set -e
if [ -n "$DATABASE_URL" ]; then
  alembic upgrade head
fi
exec "$@"
