# Miami Knows Beauty — User Stories & Feature Inventory

## Public Directory

| Feature | Status | Notes |
|---------|--------|-------|
| Neighborhood browsing | ✅ Live | `/` → neighborhood tiles |
| Category browsing | ✅ Live | `/hair-salons/`, `/nail-salons/`, etc. |
| Business detail pages | ✅ Live | `/<slug>/` with photos, hours, JSON-LD |
| JSON-LD structured data | ✅ Live | LocalBusiness + BreadcrumbList |
| Photo gallery | ✅ Live | GridFS-backed, owner-uploaded |
| Inquiry form | ✅ Live | Sends to owner + admin notify email |
| Editorial guides | ✅ Live | `/guides/<slug>/` curated "best of" pages |
| "Featured in guides" backlinks | ✅ Live | Appears on business pages when featured in guides |
| XML sitemap | ✅ Live | `/sitemap.xml` with canonical URLs |
| Canonical URLs | ✅ Live | `CANONICAL_BASE_URL=https://miami.knowsbeauty.com` |
| GA4 analytics | ✅ Live | `GA_MEASUREMENT_ID` env var |
| Google star ratings display | ✅ Live | On salon pages + JSON-LD AggregateRating; populated after API sync |
| Google Search Console | ⚠️ Pending | Verification tag ready; David needs to verify |

## Preview / Access Control

| Feature | Status | Notes |
|---------|--------|-------|
| Preview gate (email + code login) | ✅ Live | PR #144; `PREVIEW_MODE_ENABLED=true` |
| 30-day preview session cookie | ✅ Live | `preview_token` cookie |
| Allowed-email list | ✅ Live | @expertly.com, @webintensive.com, 2 personal emails |
| Public launch toggle | ✅ Ready | Set `PREVIEW_MODE_ENABLED=false` to open |

## Owner Portal

| Feature | Status | Notes |
|---------|--------|-------|
| Magic-code email login | ✅ Live | 15-min OTP, Resend |
| Owner dashboard | ✅ Live | `/owners/me` |
| Profile editing | ✅ Live | Name, description, hours, website, social |
| Photo upload/delete | ✅ Live | GridFS, hero promotion on delete |
| Claim listing | ✅ Live | Form submission → admin review |
| Inquiry notifications | ✅ Live | Owner sees contact submissions on dashboard |
| Inquiry stats | ✅ Live | Contact counts for owner analytics |

## Billing (Stripe)

| Feature | Status | Notes |
|---------|--------|-------|
| Stripe Checkout | ✅ Live | `POST /api/v1/billing/checkout` |
| Featured listing badge | ✅ Live | Active for subscribed listings |
| Subscription webhook | ✅ Live | `STRIPE_WEBHOOK_SECRET` configured in production .env as of 2026-06-11 |
| Cancellation handling | ✅ Code ready | Clears `stripe_subscription_id`; Featured badge no longer displays |
| Customer portal (self-serve cancel) | ⚠️ Pending | Enable at stripe.com/settings/billing/portal |
| Founding Partner removal | ✅ Live | Badge/cap concept removed in PR #362; do not rebuild on dead data |

## Marketing AI (Featured Tier)

| Feature | Status | Notes |
|---------|--------|-------|
| Instagram caption generator | ✅ Live & ON in prod | `/api/v1/marketing-ai/instagram-caption`; verified returning real captions on prod 2026-06-19 |
| Ad copy generator | ✅ Live & ON in prod | `/api/v1/marketing-ai/ad-copy`; returns 3 variations (Google/FB/Instagram-sized); verified on prod 2026-06-19 |
| Marketing AI on/off control | ✅ Live | DB site-setting `marketing_ai_enabled` (currently `true`) takes precedence; env var `MARKETING_AI_ENABLED` is the fallback. Toggle from `/admin/settings` → Feature Flags |

> **Launch-readiness note (2026-06-19):** The paid AI tools are confirmed ON and
> working on production. The primary on/off switch is a **database** value
> (`site_settings.marketing_ai_enabled = true`) set from the admin page, not the
> env var. If that database document were ever wiped or the setting unset, the
> feature would fall back to the env var — which on the production server is also
> `true` (both `MARKETING_AI_ENABLED` and `MARKETING_AI_ENABLED_PROD` are set), so
> the tools would stay on. The one dependency to keep an eye on: these tools call
> the centralized Expertly AI gateway, so the gateway API key (`AI_GATEWAY_KEY`)
> must stay configured in the production `.env`. It is confirmed present today.

## Admin Tools

| Feature | Status | Notes |
|---------|--------|-------|
| Claims management | ✅ Live | `/admin/claims` |
| Analytics dashboard | ✅ Live | `/admin/analytics` — includes first-send target views, action clicks, claim state, and subscription state |
| Settings / feature flags | ✅ Live | `/admin/settings` — toggle Marketing AI, preview mode, etc. |
| Google ratings sync | ✅ Live | `/admin/sync` — one-click pull from Google Places API (requires `GOOGLE_PLACES_API_KEY`) |

## Platform / Infrastructure

| Feature | Status | Notes |
|---------|--------|-------|
| Multi-tenant routing | ✅ Live | `NETWORK_DOMAINS` env var, host-based |
| Auto-deploy via Watchtower | ✅ Live | Polls GHCR every 5 min |
| CI tests | ✅ Live | GitHub Actions; 413 tests |
| Startup migrations | ✅ Live | Idempotent, tracked in `app_migrations` |
| Preview gate | ✅ Live | Email + code, 30-day cookie |

## Multi-City Expansion

| City | Businesses | Status | Subdomain |
|------|-----------|--------|-----------|
| Miami | 50 | ✅ Live | `miami.knowsbeauty.com` |
| Boca Raton | 28 | ✅ Live | `boca-raton.knowsbeauty.com` |
| Fort Lauderdale | 39 | ✅ Live | `fort-lauderdale.knowsbeauty.com` |
| Aventura | 23 | ✅ Live | `aventura.knowsbeauty.com` |
| Coral Gables | 25 | ✅ Live | `coral-gables.knowsbeauty.com` |
| Coconut Grove | 18 | ⚠️ DNS needed | `coconut-grove.knowsbeauty.com` |
| South Beach | 20 | ⚠️ DNS needed | `south-beach.knowsbeauty.com` |
| Hollywood, FL | 17 | ⚠️ DNS needed | `hollywood.knowsbeauty.com` |
| Wynwood | 19 | ⚠️ DNS needed | `wynwood.knowsbeauty.com` |
| Brickell | 18 | ⚠️ DNS needed | `brickell.knowsbeauty.com` |
| Midtown Miami | 18 | ⚠️ DNS needed | `midtown.knowsbeauty.com` |
| Delray Beach | 20 | ⚠️ DNS needed | `delray-beach.knowsbeauty.com` |
| Hallandale Beach | 18 | ⚠️ DNS needed | `hallandale-beach.knowsbeauty.com` |
| Doral | 22 | ⚠️ DNS needed | `doral.knowsbeauty.com` |
| Pompano Beach | 20 | ⚠️ DNS needed | `pompano-beach.knowsbeauty.com` |

Each city gets its own subdomain, DNS record, Traefik routing, and seed script. Adding a new city requires only: a seed script + DNS record + Traefik label entry. No code changes needed.

## Owner Journey / Walkthrough

| Feature | Status | Notes |
|---------|--------|-------|
| Walkthrough landing page | ✅ Live | `/walkthrough` — HTML + PDF link |
| PDF download | ✅ Live | `mkb-owner-journey.pdf` — 7 pages, publicly downloadable |
| Marketing AI tool mockups in PDF | ✅ Live | PR #218 — Instagram caption + ad copy generators shown with sample output |

## Roadmap / Pending

| Item | Priority | Blocked On |
|------|---------|-----------|
| Google Places API key → run rating sync | P1 | David: get key from Google Cloud Console, set `GOOGLE_PLACES_API_KEY` on server (~$2 one-time for 165 salons) |
| Stripe customer portal | P1 | David: enable at stripe.com/settings/billing/portal |
| Google Search Console verification | P1 | David: verify using meta tag |
| Public launch | P1 | David's go/no-go (set `PREVIEW_MODE_ENABLED=false` via `/admin/settings`) |
| Owner outreach email send | P1 | David sends from drafts at `/home/david/Spaces/posey/work/owner-outreach-email-draft.md` |
| Resend domain verification (knowsbeauty.com) | P2 | SPF/DKIM/MX DNS records needed |
| GPS coordinates on listings | P3 | Geocoding at import time |
| More city expansion | P3 | Platform and infrastructure ready; add seed scripts |
