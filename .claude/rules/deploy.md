# Deployment — known-around-town

## How deploy works

Code deploys (any change to Python, templates, or static files) are fully
automatic via GitHub Actions + Watchtower:
1. PR merges to `main`
2. GitHub Actions CI builds `ghcr.io/david-wi/known-around-town:latest` and pushes it
3. Watchtower polls GHCR every 5 minutes, detects the new image digest, and
   restarts the container automatically — no SSH needed

Check status after a merge:
  `ssh -p 2222 root@152.42.152.243 "docker ps --format '{{.Names}}\t{{.Status}}' | grep known"`

**Compose-file-only changes** (e.g. adding Traefik routing labels, changing env vars in
`docker-compose.prod.yml`) do NOT push a new image, so Watchtower won't pick them up.
After such a PR merges, SSH and apply manually:
  `ssh -p 2222 root@152.42.152.243 "docker compose -f /opt/known-around-town/docker-compose.prod.yml up -d backend"`

**CRITICAL:** The server has both `docker-compose.yml` (dev, has a `build:` section) and
`docker-compose.prod.yml` (production). ALWAYS use `-f docker-compose.prod.yml` when
SSHing to the server. Running bare `docker compose up -d` without the `-f` flag will use
the dev file, start a local image build, and likely take the backend down. This mistake
caused a ~3-minute outage on 2026-06-11.

## Stage

The `:stage` image is built from the `stage` branch and served at
`stage-miami.knowsbeauty.ai.devintensive.com`. Start it with:
  `docker compose --profile stage up -d`

## Feature flags

`MARKETING_AI_ENABLED` gates the AI features (caption + ad copy). Currently
off in production, on in stage. Set in `/opt/known-around-town/.env` or as
`MARKETING_AI_ENABLED_PROD` env var on the server.

## gh pr checks

`gh pr checks --watch` works correctly — waits for "Smoke tests" to pass.
Use it to confirm CI before treating a merge as complete.
`gh pr merge --squash --auto` also waits for CI before auto-merging.

## MongoDB env var name

The production MongoDB connection string env var is **`MONGODB_URL`** (NOT `MONGODB_URI`).
This is set in `/opt/known-around-town/.env` on the server. Any scripts that query
production MongoDB must use `os.environ['MONGODB_URL']` — `MONGODB_URI` is not set.

## Admin key for production

The admin key (for `/admin/login`) is in `/opt/known-around-town/.env` on the
production server under `ADMIN_COOKIE_KEY`. Fetch it with:
  `ssh -p 2222 root@152.42.152.243 "grep ADMIN_COOKIE_KEY /opt/known-around-town/.env"`

## Visual verification with Playwright

Python Playwright is available; Node.js Playwright is NOT installed in this repo.
Use `from playwright.sync_api import sync_playwright` — the package is at
`/home/david/.local/lib/python3.12/site-packages/playwright/`.
Do NOT `require('playwright')` — that will fail.
