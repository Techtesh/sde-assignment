#!/usr/bin/env bash
# Contract: ./run.sh <SIM_URL> starts the controller and runs until the scenario finishes.
# Requires Python 3.12+; Docker Compose is needed unless DATABASE_URL points to PostgreSQL.
set -euo pipefail
SIM_URL="${1:?usage: ./run.sh <SIM_URL>}"
cd "$(dirname "$0")"
if [[ -z "${DATABASE_URL:-}" ]]; then
  docker compose up -d --wait postgres
  export DATABASE_URL="postgresql://controller:controller@127.0.0.1:55432/controller"
fi
if [[ -n "${CONTROLLER_PROFILE:-}" ]]; then
  exec "${PYTHON:-python}" -m cProfile -o "$CONTROLLER_PROFILE" -m controller --url "$SIM_URL"
fi
exec "${PYTHON:-python}" -m controller --url "$SIM_URL"
