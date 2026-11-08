#!/usr/bin/env bash
# Requires Docker Compose unless DATABASE_URL points to an existing PostgreSQL database.
set -euo pipefail
SIM_URL="${1:?usage: ./run.sh <SIM_URL>}"
cd "$(dirname "$0")"
if [[ -z "${DATABASE_URL:-}" ]]; then
  docker compose up -d --wait postgres
  export DATABASE_URL="postgresql://controller:controller@127.0.0.1:55432/controller"
fi
exec "${PYTHON:-python}" -m controller --url "$SIM_URL"
