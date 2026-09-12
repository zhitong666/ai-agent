#!/usr/bin/env bash
set -euo pipefail

docker compose build
docker compose up -d

for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "backend is healthy"
    break
  fi
  sleep 1
done

curl -fsS http://localhost:5173/ >/dev/null
echo "frontend is running"
echo "Docker MVP smoke test passed"