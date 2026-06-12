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

| Flag | What it controls | Safe to enable when |
|---|---|---|
| `PREVIEW_MODE_ENABLED` | Gates the entire site behind email+code login | Ready to open to the public |
| `MARKETING_AI_ENABLED` | Enables the AI caption and ad copy endpoints for Featured subscribers | An Anthropic API key is confirmed configured and the AI tools are ready to serve |

### Enabling marketing AI tools

```bash
# Add/update in /opt/known-around-town/.env
MARKETING_AI_ENABLED=true

# Apply (no image pull needed)
docker compose -f docker-compose.prod.yml restart backend
```

If `MARKETING_AI_ENABLED` is blank or `false`, the Instagram caption and ad copy endpoints return HTTP 404, so subscribers who try to use these tools get a silent failure. **This flag must be `true` before launch.**

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
