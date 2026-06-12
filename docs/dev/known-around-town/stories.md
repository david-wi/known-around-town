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
| Founding Partner badge | ✅ Live | Permanent; first 25 paying owners |
| Subscription webhook | ✅ Live | `STRIPE_WEBHOOK_SECRET` configured in production .env as of 2026-06-11 |
| Cancellation handling | ✅ Code ready | Clears `stripe_subscription_id`, badge stays |
| Customer portal (self-serve cancel) | ⚠️ Pending | Enable at stripe.com/settings/billing/portal |
| Founding partner cap | ✅ Live | 25 slots, configurable via `FOUNDING_PARTNER_CAP` |

## Admin Tools

| Feature | Status | Notes |
|---------|--------|-------|
| Claims management | ✅ Live | `/admin/claims` |
| Analytics dashboard | ✅ Live | `/admin/analytics` |

## Platform / Infrastructure

| Feature | Status | Notes |
|---------|--------|-------|
| Multi-tenant routing | ✅ Live | `NETWORK_DOMAINS` env var, host-based |
| Auto-deploy via Watchtower | ✅ Live | Polls GHCR every 5 min |
| CI tests | ✅ Live | GitHub Actions; 372 tests |
| Startup migrations | ✅ Live | Idempotent, tracked in `app_migrations` |
| Preview gate | ✅ Live | Email + code, 30-day cookie |

## Roadmap / Pending

| Item | Priority | Blocked On |
|------|---------|-----------|
| Stripe customer portal | P1 | David: enable at stripe.com |
| Google Search Console verification | P1 | David: verify using meta tag |
| Public launch | P1 | David's go/no-go (turn off preview gate, send outreach) |
| "Knows" vertical domains (9 available) | P2 | David: fund Dynadot account ($~196) |
| Owner outreach email send | P2 | David sends from drafts at `/home/david/Spaces/posey/work/owner-outreach-email-draft.md` |
| Resend domain verification (knowsbeauty.com) | P2 | SPF/DKIM/MX DNS records needed |
| GPS coordinates on listings | P3 | Geocoding at import time |
| Multi-city expansion | P3 | Platform ready; needs data |
