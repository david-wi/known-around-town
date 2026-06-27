# Miami Knows Beauty — Architecture

## Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12, FastAPI |
| Templates | Jinja2 + Tailwind CSS (compiled at build time) |
| Database | MongoDB Atlas (`who_knows_local` database) |
| File storage | MongoDB GridFS (bucket: `business_photos`) |
| Email | Resend API (`noreply@knowsbeauty.ai.devintensive.com`) |
| Billing | Stripe (restricted key `rk_live_...`, checkout + subscriptions) |
| Container | Docker, single `backend` service |
| Reverse proxy | Traefik (on shared DigitalOcean droplet) |
| Auto-deploy | Watchtower (polls GHCR every 5 minutes for new `:latest` images) |
| CI | GitHub Actions (`.github/workflows/ci.yml`) |

## Deployment

- **Server**: `root@152.42.152.243` port 2222 (DigitalOcean droplet)
- **Working dir**: `/opt/known-around-town/`
- **Compose**: `docker compose -f docker-compose.prod.yml` — **always use the `-f` flag; bare `docker compose` uses the dev file and kills the backend**
- **Deploy flow**: push to `main` → GitHub Actions builds image → Watchtower pulls and restarts container (within 5 minutes)
- **Env vars**: `/opt/known-around-town/.env` — changes require a manual `docker compose -f docker-compose.prod.yml restart backend` because Watchtower only triggers on image changes, not compose file or env changes
- **Logs**: `docker compose -f docker-compose.prod.yml logs -f backend`

## Multi-Tenant Architecture

The platform supports multiple "networks" (e.g., beauty, wellness, health) and multiple cities per network. Each combination gets its own subdomain.

**Domain routing**: `NETWORK_DOMAINS` env var maps `slug:domain` pairs separated by commas. The app reads the incoming `Host` header and resolves the matching network slug. This determines which city/neighborhood/category data to serve.

**Active networks** (as of 2026-06-12):
- `beauty:knowsbeauty.com` and `beauty:knowsbeauty.ai.devintensive.com` — Miami beauty, 27 verified businesses
- `wellness:knowswellness.com` and `wellness:knowswellness.ai.devintensive.com` — Miami wellness, no businesses yet
- `health:knowshealth.ai.devintensive.com` — Miami health, no businesses yet (knowshealth.com DNS not configured)

**Subdomains as city slugs**: Any subdomain that doesn't match a known city slug is treated as a city lookup. `miami.knowsbeauty.com` → city=`miami`, network=`beauty`. Adding a new city requires a seed script + DNS record only — no code changes.

**`stage-` prefix support**: `stage-miami.knowsbeauty.com` routes to the same Miami beauty content as `miami.knowsbeauty.com`. The `_match_suffix()` function in `tenant.py` strips the `stage-` prefix before the city lookup. This is purely a code-staging mechanism — the same production DB is used; there's no separate staging dataset.

## Traefik Router Structure

**Split routers per domain type** (PR #163, 2026-06-12): Each vertical has two Traefik routers:
- `kat-<network>-com` — the public `.com` domains (e.g., `miami.knowsbeauty.com`, `www.miami.knowsbeauty.com`, `stage-miami.knowsbeauty.com`)
- `kat-<network>-dev` — the internal dev subdomains (e.g., `miami.knowsbeauty.ai.devintensive.com`)

**Why split**: Traefik's certResolver uses the **first `Host()` entry** in a router rule as the main domain for the TLS cert it issues. If dev and `.com` domains share one router, the cert's CN becomes the dev subdomain — browsers don't error (the `.com` domains are still in the SANs) but it's architecturally wrong. Separate routers ensure each group gets a cert whose CN matches the primary audience.

**Adding a new vertical's `.com` domain**: Add a `kat-<network>-com` router block to `docker-compose.prod.yml`, configure DNS, then `docker compose -f docker-compose.prod.yml up -d --no-deps backend` on the server to reload Traefik labels. Watchtower does NOT pick up compose file changes.

## Data Model (MongoDB Collections)

| Collection | Purpose |
|-----------|---------|
| `networks` | Top-level brand (e.g., "Knows Beauty") |
| `cities` | City under a network (e.g., "Miami") |
| `neighborhoods` | Neighborhood within a city |
| `categories` | Service category (e.g., "Hair Salons") |
| `businesses` | Salon listing — the core entity |
| `editorial_guides` | Curated "Best of" guide pages |
| `business_claims` | Ownership claim submissions |
| `business_inquiries` | Contact form submissions |
| `owner_sessions` | Passwordless magic-code sessions for owner login |
| `owner_magic_codes` | 15-minute OTP codes for owner authentication |
| `preview_codes` | 15-minute OTP codes for preview gate access |
| `preview_sessions` | 30-day sessions after preview gate login |
| `copy_blocks` | Editable copy for pages (scoped: global/network/city/neighborhood/category/business) |
| `app_migrations` | One-time migration tracking |
| `stripe_events` | Stripe webhook idempotency log |

**Business document key fields**:
- `status`: `draft` | `live` | `archived`
- `claim_status`: `unclaimed` | `pending` | `claimed` | `verified`
- `stripe_customer_id`: set at checkout, **never cleared**
- `stripe_subscription_id`: set at checkout, **cleared on cancellation**
- `is_founding_partner`: **dead field** — the Founding Partner concept was removed entirely (PR #362). The app no longer grants, counts, or displays it. The field and the `clear-seeded-founding-partner-flags` startup migration are intentionally left in place as harmless dead data; do not build on them.

## Preview Gate

FastAPI middleware (`app.middleware.preview_gate.PreviewGateMiddleware`) wraps every route. When `PREVIEW_MODE_ENABLED=true`:

1. Checks for a valid `preview_token` cookie (32-byte hex, stored as SHA-256 hash in `preview_sessions`)
2. If missing/invalid → redirects to `/preview-login`
3. Bypassed routes: `/health`, `/api/v1/billing/webhook`, `/preview-login`, `/preview-login/…`, `/assets/…`, `/media/…`
4. Allowed emails: `@expertly.com`, `@webintensive.com`, `aggiewaggie06@gmail.com`, `karissa.ostoski@gmail.com`, `david@bodnick.com`, `david@wisdev.com`

To disable the gate (public launch): set `PREVIEW_MODE_ENABLED=false` in `/opt/known-around-town/.env` and restart the container. No code deploy needed.

## Key Environment Variables

| Variable | Required | Notes |
|---------|---------|-------|
| `MONGODB_URL` | Yes | Atlas connection string (`mongodb+srv://...`) |
| `MONGODB_DATABASE` | Yes | Must be `who_knows_local` |
| `NETWORK_DOMAINS` | Yes | Comma-separated `slug:domain` pairs |
| `ADMIN_API_KEY` | Yes | Bearer token for write API endpoints |
| `STRIPE_SECRET_KEY` | For billing | `rk_live_...` restricted key |
| `STRIPE_WEBHOOK_SECRET` | For billing | `whsec_...` from Stripe dashboard |
| `STRIPE_PRICE_ID_PRO` | For billing | Fallback `price_...` for the $29/month Featured plan |
| `STRIPE_PRICE_IDS_BY_CITY` | Optional billing override | Comma-separated `city_slug:price_...` map for city-specific Knows Beauty Products/Prices, e.g. `miami:price_...,austin:price_...` |
| `RESEND_API_KEY` | For email | Owner + preview magic codes |
| `OWNER_SESSION_SECRET` | For owner auth | Random secret; losing it logs out all owners |
| `CANONICAL_BASE_URL` | For SEO | `https://miami.knowsbeauty.com` |
| `PREVIEW_MODE_ENABLED` | For gate | `true` (private) or `false` (public) |
| `GA_MEASUREMENT_ID` | For analytics | Google Analytics 4 measurement ID |
| `GOOGLE_SITE_VERIFICATION` | For GSC | Meta tag for Search Console verification |
| `ALLOW_LOCAL_MONGODB` | Dev only | `true` to allow localhost Mongo |
| `VAPI_ASSISTANT_MODEL_PROVIDER` | For Concierge voice | VAPI provider for the live phone assistant model loop (default `openai`) |
| `VAPI_ASSISTANT_MODEL` | For Concierge voice | VAPI model for the live phone assistant model loop (default `gpt-4o`) |

## URL Structure

```
/                              → city listing (or single-city redirect)
/<neighborhood-slug>/          → neighborhood page
/<category-slug>/              → category page  
/<neighborhood>/<category>/    → filtered listing
/<slug>/                       → business detail page
/guides/                       → editorial guide list
/guides/<slug>/                → editorial guide detail
/owners/                       → owner portal home
/owners/me                     → owner dashboard
/owners/login                  → magic code login
/admin/claims                  → admin claims management
/admin/analytics               → admin analytics
/preview-login                 → preview gate login (standalone page)
/sitemap.xml                   → XML sitemap
/api/v1/…                     → JSON API
```

## Stripe Billing Flow

1. Owner clicks "Subscribe" on their dashboard → POST `/api/v1/billing/checkout` → Stripe Checkout Session URL returned. If `STRIPE_PRICE_IDS_BY_CITY` contains the listing city slug, checkout uses that city-specific Price; otherwise it falls back to `STRIPE_PRICE_ID_PRO`.
2. Owner completes payment on Stripe → redirected back to `/owners/me?checkout=success`
3. Stripe fires `checkout.session.completed` webhook → `/api/v1/billing/webhook`
4. Webhook sets `stripe_customer_id`, `stripe_subscription_id`, `featured.tier=premium`, `featured.enabled=true` (it no longer touches `is_founding_partner` — that concept was removed in PR #362)
5. If owner cancels: Stripe fires `customer.subscription.deleted` → webhook downgrades `featured` to free and clears `stripe_subscription_id`

**Statement descriptor**: `EXPERTLY*KNOWSBEAUTY`

**Webhook 503**: The webhook endpoint intentionally returns 503 when `STRIPE_WEBHOOK_SECRET` is empty — this is correct behavior, not a bug.
