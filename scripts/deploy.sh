#!/usr/bin/env bash
# Pull the latest image, restart the container, and run the seed scripts the
# first time. Idempotent — re-runs do not re-create data because the seed
# scripts upsert by stable keys (network slug, city slug, business slug).
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/known-around-town}"
cd "$REPO_DIR"

git fetch --quiet
git reset --hard origin/main

# Build the image locally — this server doesn't use a registry pipeline yet.
docker build -t ghcr.io/david-wi/known-around-town:latest ./backend

docker compose -p known-around-town -f docker-compose.prod.yml up -d

echo "Waiting for /health..."
for i in {1..30}; do
  cid=$(docker ps -q -f name=known-around-town-backend)
  if [ -n "$cid" ] && docker exec "$cid" curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "healthy"
    break
  fi
  sleep 1
done

# Seed (upsert) the catalog. Safe to re-run.
docker compose -p known-around-town -f docker-compose.prod.yml exec -T backend python -m seed.seed_networks
docker compose -p known-around-town -f docker-compose.prod.yml exec -T backend python -m seed.seed_miami

echo "Deploy complete."
