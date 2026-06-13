#!/usr/bin/env bash
# Pull the latest code, build the image, restart the container, and run the
# seed scripts the first time. Idempotent — re-runs do not re-create data
# because the seed scripts upsert by stable keys (network slug, city slug,
# business slug).
#
# Two deploy targets are supported, selected by the DEPLOY_TARGET env var:
#
#   DEPLOY_TARGET=latest  (default)
#     Pulls origin/main, builds the image tagged `:latest`, and (re)starts
#     the production container. This is what the auto-deploy webhook runs
#     on every push to the `main` branch.
#
#   DEPLOY_TARGET=stage
#     Pulls origin/stage, builds the image tagged `:stage`, and (re)starts
#     the preview container under Compose's `stage` profile so it doesn't
#     collide with production. This is what the auto-deploy webhook runs
#     on every push to the `stage` branch — for previewing a proposed
#     change at stage-miami.knowsbeauty.ai.devintensive.com (and the
#     wellness / health equivalents) before promoting it to main.
#
# Both targets share the same compose file and the same MongoDB; only the
# image tag, the branch checked out, and the Compose profile differ.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/known-around-town}"
# WHY: Default to 'latest' so existing callers (including the original
# auto-deploy webhook before stage support landed) keep working unchanged.
DEPLOY_TARGET="${DEPLOY_TARGET:-latest}"

case "$DEPLOY_TARGET" in
  latest)
    BRANCH="main"
    IMAGE_TAG="latest"
    # WHY: Empty profile arg means production-only services start. The
    # stage service in docker-compose.prod.yml is gated by `profiles:
    # ["stage"]`, so it stays dormant on a normal production deploy.
    COMPOSE_PROFILE_ARGS=()
    # WHY: target the production service explicitly so future compose
    # profiles cannot accidentally start or recreate preview services.
    COMPOSE_SERVICE="backend"
    SEED_AFTER_DEPLOY="true"
    ;;
  stage)
    BRANCH="stage"
    IMAGE_TAG="stage"
    # WHY: --profile stage activates the backend-stage service in the
    # compose file. The production backend keeps running untouched
    # because Compose only stops/recreates the services it can see in
    # the active profile set.
    COMPOSE_PROFILE_ARGS=(--profile stage)
    # WHY: Compose includes unprofiled services whenever any profile is
    # enabled. Targeting backend-stage prevents a stage deploy from
    # restarting the production backend.
    COMPOSE_SERVICE="backend-stage"
    # WHY: Stage shares the production MongoDB, so re-seeding from the
    # stage branch is unnecessary and risks rewriting prod content if
    # the stage branch carries seed changes we haven't approved yet.
    SEED_AFTER_DEPLOY="false"
    ;;
  *)
    echo "Unknown DEPLOY_TARGET='$DEPLOY_TARGET' (expected 'latest' or 'stage')" >&2
    exit 2
    ;;
esac

cd "$REPO_DIR"

git fetch --quiet
git reset --hard "origin/$BRANCH"

# Build the image locally — this server doesn't use a registry pipeline yet.
docker build -t "ghcr.io/david-wi/known-around-town:$IMAGE_TAG" ./backend

# WHY: the image tag is stable (:latest or :stage). Without force-recreate,
# Compose may keep the old container running after a code-only rebuild
# because the service config did not change.
docker compose -p known-around-town "${COMPOSE_PROFILE_ARGS[@]}" \
  -f docker-compose.prod.yml up -d --force-recreate "$COMPOSE_SERVICE"

# WHY: Compose appends `-N` (replica index) to the container name, so the
# real container names are `known-around-town-backend-1` and
# `known-around-town-backend-stage-1`. We pin to the exact name via a
# `^...-\d+$` regex anchor so a bare `name=known-around-town-backend`
# filter does not accidentally match the stage container too.
if [ "$DEPLOY_TARGET" = "latest" ]; then
  CONTAINER_FILTER='^known-around-town-backend-[0-9]+$'
else
  CONTAINER_FILTER='^known-around-town-backend-stage-[0-9]+$'
fi

echo "Waiting for /health on $CONTAINER_FILTER..."
for i in {1..30}; do
  cid=$(docker ps -q -f name="$CONTAINER_FILTER")
  if [ -n "$cid" ] && docker exec "$cid" curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "healthy"
    break
  fi
  sleep 1
done

# Seed (upsert) the catalog. Safe to re-run, but only for the production
# target — see SEED_AFTER_DEPLOY rationale above.
#
# WHY KAT_ALLOW_PRODUCTION_RESET=true: the seed scripts now refuse to run
# against a production database unless this explicit confirmation is set,
# because they DELETE stale records as part of re-seeding and once wiped the
# live database when run by mistake. This deploy step IS the intentional
# production seed, so it sets the flag on purpose. A human running the seed by
# hand from a laptop will not have it set, so their accidental run aborts
# instead of wiping production. `-e` passes the flag into the container's
# environment for that one exec only.
if [ "$SEED_AFTER_DEPLOY" = "true" ]; then
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_networks
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_miami
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_boca_raton
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_fort_lauderdale
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_aventura
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_coral_gables
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_coconut_grove
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_hollywood
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_south_beach
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_wynwood
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_brickell
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_midtown
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_delray_beach
  docker compose -p known-around-town -f docker-compose.prod.yml exec -T \
    -e KAT_ALLOW_PRODUCTION_RESET=true backend python -m seed.seed_hallandale_beach
fi

echo "Deploy complete ($DEPLOY_TARGET)."
