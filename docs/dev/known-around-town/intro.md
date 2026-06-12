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

## Current Status (as of 2026-06-12)

- **Production domain**: `miami.knowsbeauty.com` (Dynadot DNS → DO server)
- **Dev/staging domain**: `miami.knowsbeauty.ai.devintensive.com`
- **Preview mode**: ON — only allowed emails (@expertly.com, @webintensive.com, aggiewaggie06@gmail.com, karissa.ostoski@gmail.com) can access the site; turn off to launch publicly
- **Stripe billing**: fully live — checkout and webhook processing both active as of 2026-06-11
- **Directory size**: 20 verified beauty businesses (post-cleanup; 30 ghost/closed listings archived 2026-06-12); wellness network at miami.knowswellness.com has ~50 businesses
- **Founding Partner cap**: 25 subscribers (configurable via `FOUNDING_PARTNER_CAP` env var)
- **Second vertical**: miami.knowswellness.com is live in the database behind the preview gate; ready to open alongside beauty
- **Ghost removal audit**: 30 confirmed ghost listings archived 2026-06-12; full evidence at `~/Spaces/posey/notes/ghost-removals-evidence.md`

## GitHub

Repo: `david-wi/known-around-town` — private repo on GitHub.
Container image: `ghcr.io/david-wi/known-around-town:latest`

## Operator

David Bodnick (`david@bodnick.com` / `david@expertly.com`). AI Product Manager: Posey (Slack: `#agent-posey-knows-beauty` in expertlyhq workspace).
