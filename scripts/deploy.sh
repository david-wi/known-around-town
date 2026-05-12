#!/usr/bin/env bash
# Pull the latest image, restart the container, and run the seed scripts the
# first time. Idempotent — re-runs do not re-create data because the seed
# scripts upsert by stable keys (network slug, city slug, business slug).
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/who-knows-local}"
cd "$REPO_DIR"

git fetch --quiet
git reset --hard origin/main

# Build the image locally — this server doesn't use a registry pipeline yet.
docker build -t ghcr.io/david-wi/who-knows-local:latest ./backend

docker compose -p who-knows-local -f docker-compose.prod.yml up -d

echo "Waiting for /health..."
for i in {1..30}; do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "healthy"
    break
  fi
  sleep 1
done

# Seed (upsert) the catalog. Safe to re-run.
docker compose -p who-knows-local -f docker-compose.prod.yml exec -T backend python -m seed.seed_networks
docker compose -p who-knows-local -f docker-compose.prod.yml exec -T backend python -m seed.seed_miami

echo "Deploy complete."
