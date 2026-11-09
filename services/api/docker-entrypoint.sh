#!/bin/sh
set -e

if [ "${DINEMATE_MIGRATE_ON_START:-false}" = "true" ]; then
  alembic upgrade head
fi

if [ "${DINEMATE_SEED_IF_EMPTY:-false}" = "true" ]; then
  python -m app.seed --if-empty
fi

if [ -n "${DINEMATE_HUB_TOKEN:-}" ]; then
  python -m app.testfeeds.hub_setup
fi

exec "$@"
