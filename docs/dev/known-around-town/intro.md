# Miami Knows Beauty — Product Introduction

**Miami Knows Beauty** (`miami.knowsbeauty.com`) is a curated local directory of beauty salons in Miami, Florida. It is the first deployment of the "Known Around Town" (KAT) multi-tenant directory platform.

## Mission

Help Miami residents find the best local beauty salons — and help those salon owners attract new clients, build credibility, and grow through a low-cost subscription.

## What It Is

A server-side-rendered directory website with:
- **Public directory** — neighborhood and category browsing, business detail pages, editorial guides
- **Owner portal** — salon owners claim and manage their listing, upload photos, see inquiry stats
- **Subscription billing** — Stripe-powered "Founding Partner" subscriptions at $29/month; first 25 subscribers get a permanent badge
- **Preview gate** — the site is currently private (invitation-only) behind an email + 6-digit code login, to be disabled when the site goes fully public

## Business Model

Salon owners pay **$29/month** to become a "Founding Partner." Benefits include:
- Permanent "Founding Partner" badge on their listing (stays even if they cancel)
- Enhanced featured placement
- Priority lead delivery from the inquiry form

David (the operator) sends outreach emails to Miami salon owners. Owners click a link to claim their listing and subscribe.

## Current Status (as of 2026-06-11)

- **Production domain**: `miami.knowsbeauty.com` (Dynadot DNS → DO server)
- **Dev/staging domain**: `miami.knowsbeauty.ai.devintensive.com`
- **Preview mode**: ON — only allowed emails (@expertly.com, @webintensive.com, aggiewaggie06@gmail.com, karissa.ostoski@gmail.com) can access the site
- **Stripe billing**: live key configured; webhook secret pending (checkout works but subscription webhooks not yet processed)
- **Directory size**: 147 businesses seeded from Miami public data (all published as "live")
- **Founding Partner cap**: 25 subscribers (configurable via `FOUNDING_PARTNER_CAP` env var)

## GitHub

Repo: `david-wi/known-around-town` — private repo on GitHub.
Container image: `ghcr.io/david-wi/known-around-town:latest`

## Operator

David Bodnick (`david@bodnick.com` / `david@expertly.com`). AI Product Manager: Posey (Slack: `#agent-posey-knows-beauty` in expertlyhq workspace).
