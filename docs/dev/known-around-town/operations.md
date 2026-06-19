# Miami Knows Beauty — Operations

## Production Server

- **SSH**: `ssh -p 2222 root@152.42.152.243`
- **Working dir**: `/opt/known-around-town/`
- **Env file**: `/opt/known-around-town/.env`
- **Compose file**: `docker-compose.prod.yml`

**CRITICAL**: Always use `docker compose -f docker-compose.prod.yml` — bare `docker compose` defaults to the dev compose file and kills the production backend.

## Common Commands

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f backend

# Restart backend (after .env changes, compose file changes)
docker compose -f docker-compose.prod.yml restart backend

# Full restart (pull latest image manually)
docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d

# Health check
curl http://localhost:8000/health

# Run database migrations manually (they auto-run on startup)
docker compose -f docker-compose.prod.yml exec backend python -m app.database

# Seed production data (DANGEROUS — wipes and reseeds businesses)
# Only safe via deploy script with KAT_ALLOW_PRODUCTION_RESET=true
```

## Deployment Flow

1. Commit to `main` → GitHub Actions builds Docker image → pushes to GHCR as `:latest`
2. Watchtower on the server polls GHCR every 5 minutes → detects new image → pulls and restarts `backend` container
3. No manual action needed for code-only changes

**Merging a PR (there IS a required CI check):** `main` has branch protection
requiring the **"Smoke tests"** status check (from the "CI" workflow) to pass
before merge. Merge with `gh pr merge <n> --auto --squash` and let it land
automatically once Smoke tests go green — a PR will show `mergeStateStatus:
BLOCKED` with `mergeable: MERGEABLE` while that check is still running, which is
normal, not an error. (`gh pr checks` may print a 401 because the deploy webhook
is a non-Actions check; use `gh pr view <n> --json statusCheckRollup` to watch
the real "Smoke tests" run instead.) After merge, a second "CI" run on the merge
commit builds and pushes the new `:latest`; the prod backend container is
typically recreated within ~1 minute. Verify the new code is live by exec-ing
into `known-around-town-backend-1` and grepping the changed file — the image has
no git repo baked in, so check by content, not by SHA.

**Env var changes**: Watchtower does NOT re-read `.env` or the compose file on image updates. After changing `.env`, you must run:
```bash
docker compose -f docker-compose.prod.yml restart backend
```

**Compose file changes**: Same — manual restart needed.

## Adding a New Environment Variable

1. Add to `/opt/known-around-town/.env` on the production server
2. Add the variable to the `environment:` block in `docker-compose.prod.yml` in the repo (with `${VAR_NAME:-}` pattern)
3. Commit and push the compose file change
4. Restart the container on the server

If you skip step 2, the env var is silently invisible to the container even if it's in `.env`.

## Stripe Setup

**Current state**: Fully live as of 2026-06-11. Checkout, webhook, and Founding Partner badge all operational.

- Checkout creates a session via `POST /api/v1/billing/checkout`
- Webhook at `POST /api/v1/billing/webhook` receives `checkout.session.completed` and `customer.subscription.deleted`
- `STRIPE_WEBHOOK_SECRET` is set in production `.env`
- Founding Partner badge (first 25 subscribers, permanent) is working

**Stripe product**: `prod_UgggS2CyiLgD52`
**Stripe price**: `price_1ThJJFAIj5oq6xI8oejLDzvu` ($29/month)
**Statement descriptor**: `EXPERTLY*KNOWSBEAUTY`
**Customer portal**: Needs to be enabled at stripe.com/settings/billing/portal (David action — 2-min task)

## DNS

- **Domain**: `knowsbeauty.com` at Dynadot
- **A record**: `miami.knowsbeauty.com` → `174.138.81.31` (TTL 300)
- **DNS provider**: Dynadot (switched from parking to Dynadot DNS; `set_dns2` API replaces ALL records)
- **Traefik cert**: Let's Encrypt HTTP-01 for each listed hostname

## Database

- **Provider**: MongoDB Atlas
- **Database name**: `who_knows_local` (historical name — do NOT rename; production data is here)
- **Motor client**: `tz_aware=True`
- **Indexes**: created at startup via `ensure_indexes()` in `database.py`
- **Migrations**: one-time migrations in `run_startup_migrations()` (idempotent, tracked in `app_migrations`)

**Access**: Only from Atlas-allowlisted IPs. To run direct queries, use the production container or an allowlisted machine.

## Feature Flags

All feature flags are set in `/opt/known-around-town/.env` and take effect after a container restart.

| Flag | What it controls | Current prod state (verified 2026-06-19) |
|---|---|---|
| `PREVIEW_MODE_ENABLED` | Gates the entire site behind email+code login | ON (`preview_mode_enabled = true` in the `site_settings` DB doc) — site is still private |
| Marketing AI (caption + ad copy) | Enables the AI caption and ad copy endpoints for Featured subscribers | **ON and verified working** — primary control is the DB site-setting `marketing_ai_enabled = true` |

> **How the Marketing-AI on/off switch actually works (precedence matters):**
> The code reads `get_marketing_ai_enabled()`, which checks the **database** first
> (`site_settings.marketing_ai_enabled`, set from the `/admin/settings` page) and
> only falls back to the env var when the DB value is unset. **The DB value wins.**
> As of 2026-06-19 the production DB has `marketing_ai_enabled = true`, so the
> tools are ON — independent of any env var. Belt-and-suspenders: the production
> `.env` also has both `MARKETING_AI_ENABLED=true` and `MARKETING_AI_ENABLED_PROD=true`,
> so even if the DB value were removed, the env-var fallback keeps the tools on.
>
> **Env-var naming:** Per `docker-compose.prod.yml`, the prod service maps the
> container's `MARKETING_AI_ENABLED` from the host's `MARKETING_AI_ENABLED_PROD`
> (`${MARKETING_AI_ENABLED_PROD:-}`); the staging service maps it from
> `MARKETING_AI_ENABLED` (default `true`). Today the host `.env` sets both to
> `true`, so the env-var fallback is on regardless of which mapping applies.
>
> **LLM provider:** These tools do NOT use an Anthropic key on the server. They
> call the centralized Expertly AI gateway
> (`admin-api.ai.devintensive.com/api/public/ai-config/call`, use case
> `marketing_caption`) using the `AI_GATEWAY_KEY` env var — confirmed present in
> the prod `.env`. There is intentionally no `ANTHROPIC_API_KEY` on the server,
> matching the Expertly convention that production servers don't hold model keys.

### Turning marketing AI off or on (if ever needed)

Preferred path — the admin page (no restart, takes effect immediately):

```
/admin/settings → Feature Flags → Marketing AI toggle
```

This writes `marketing_ai_enabled` into the `site_settings` DB doc, which the
code reads on every request. The env vars below are only the fallback for when
the DB value is unset.

```bash
# Fallback env path (only used when the DB value is unset)
# Add/update in /opt/known-around-town/.env, then restart:
MARKETING_AI_ENABLED_PROD=true
docker compose -f docker-compose.prod.yml restart backend
```

If the feature is off by every path (DB unset AND env vars false/blank), the
Instagram caption and ad copy endpoints return HTTP 404, and subscribers who try
to use these tools get a silent failure.

## Preview Gate

Toggle via env var — no code deploy needed:
```bash
# Open the site to the public
echo "PREVIEW_MODE_ENABLED=false" >> /opt/known-around-town/.env
docker compose -f docker-compose.prod.yml restart backend

# Close the site (return to preview mode)
# Edit .env to set PREVIEW_MODE_ENABLED=true
# restart
```

Allowed emails (hardcoded in middleware):
- `@expertly.com` (any address)
- `@webintensive.com` (any address)
- `aggiewaggie06@gmail.com`
- `karissa.ostoski@gmail.com`

## Monitoring

- **Health endpoint**: `https://miami.knowsbeauty.com/health` → `{"status": "ok"}`
- **Error logs**: https://admin.ai.devintensive.com/error-logs (Expertly centralized error tracker)
- **Slack channel**: `#agent-posey-knows-beauty` (expertlyhq) — Posey posts status updates here

## Re-Seeding Production (Emergency Only)

The seed scripts wipe and recreate neighborhoods, categories, and businesses. They are guarded and will refuse to run without explicit opt-in.

```bash
# Deploy script path — it passes KAT_ALLOW_PRODUCTION_RESET=true
cat /opt/known-around-town/scripts/deploy.sh
```

The normal deploy (`push to main → CI → Watchtower`) does NOT run seeds. Seeds only run when `SEED_AFTER_DEPLOY=true` is set in the deploy script environment.

## Email Sending (Resend)

- `RESEND_API_KEY` must be set in production `.env`
- From address: `OWNER_EMAIL_FROM_ADDRESS` (default: `noreply@knowsbeauty.ai.devintensive.com`)
- Preview gate codes sent from: same Resend key

**Pending**: SPF/DKIM/MX for `knowsbeauty.com` needed to send from `david@knowsbeauty.com` domain (Resend domain verification not yet complete).
