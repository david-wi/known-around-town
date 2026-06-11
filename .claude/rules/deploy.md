# Deployment — known-around-town

## How deploy works

GitHub Actions CI runs smoke tests on every PR and push to `main`. The server
also runs an auto-deploy webhook that fires on every push to `main`. It runs
`/opt/known-around-town/scripts/deploy.sh`, which:
1. `git pull origin main` into `/opt/known-around-town`
2. Builds `ghcr.io/david-wi/known-around-town:latest` from `backend/Dockerfile`
3. Restarts the container via `docker compose up -d`

After merging a PR, the container typically restarts within ~8–10 seconds of
the merge (the webhook fires almost immediately). Check with:
  `ssh -p 2222 root@152.42.152.243 "docker ps --format '{{.Names}}\t{{.Status}}' | grep known"`

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
