#!/usr/bin/env bash
# Boot the dev stack: Postgres + Redis containers, DB migrations, then the API with auto-reload.
# Usage: ./run.sh [extra uvicorn args, e.g. --port 9000]
set -euo pipefail
cd "$(dirname "$0")"

# Use the project venv if there is one, otherwise whatever python3 is on PATH.
# Override with: PYTHON=/path/to/python ./run.sh
if [[ -z "${PYTHON:-}" ]]; then
  if [[ -x .venv/bin/python ]]; then PYTHON=.venv/bin/python; else PYTHON=python3; fi
fi

wait_for() {
  local name=$1; shift
  for _ in $(seq 1 30); do
    if "$@" >/dev/null 2>&1; then echo "$name is ready."; return 0; fi
    sleep 1
  done
  echo "$name did not become ready in 30s." >&2
  exit 1
}

COMPOSE=(docker compose -f docker/postgres.yaml -f docker/redis.yaml)

# Tear the containers down when the script exits (Ctrl+C, a failed step, or uvicorn stopping).
cleanup() {
  trap '' INT TERM  # don't let a second Ctrl+C interrupt the teardown
  echo
  echo "Stopping Postgres and Redis..."
  "${COMPOSE[@]}" down
}

echo "Starting Postgres and Redis..."
"${COMPOSE[@]}" up -d
trap cleanup EXIT

# -h localhost: during first-time init Postgres only listens on its socket, so this waits for the real server.
wait_for Postgres docker exec pg-user pg_isready -q -h localhost -U postgres
wait_for Redis bash -c "docker exec redis redis-cli ping | grep -qE 'PONG|NOAUTH'"

echo "Applying database migrations..."
"$PYTHON" -m alembic upgrade head

# Only watch app/ — postgres/ holds Docker-owned data the reloader can't read.
# Not exec'd, so the shell stays alive to run the cleanup trap after uvicorn exits.
"$PYTHON" -m uvicorn app.main:app --reload --reload-dir app "$@"
