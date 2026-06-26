# Miami Knows Beauty — Product Introduction

**Miami Knows Beauty** (`miami.knowsbeauty.com`) is a curated local directory of beauty salons in Miami, Florida. It is the first deployment of the "Known Around Town" (KAT) multi-tenant directory platform.

## Mission

Help Miami residents find the best local beauty salons — and help those salon owners attract new clients, build credibility, and grow through a low-cost subscription.

## What It Is

A server-side-rendered directory website with:
- **Public directory** — neighborhood and category browsing, business detail pages, editorial guides
- **Owner portal** — salon owners claim and manage their listing, upload photos, generate AI marketing copy, and manage subscription status
- **Subscription billing** — Stripe-powered Featured subscriptions at $29/month
- **Preview gate** — the site is currently private (invitation-only) behind an email + 6-digit code login, to be disabled when the site goes fully public

## Business Model

Salon owners pay **$29/month** for a Featured listing. Benefits include:
- Premium placement in relevant directory results
- Featured listing badge while subscribed
- AI marketing tools for Instagram captions, profile descriptions, and ad copy
- Priority lead delivery from the inquiry form

David (the operator) sends outreach emails to Miami salon owners. Owners click a link to claim their listing and subscribe.

## Current Status (as of 2026-06-12)

- **Production domain**: `miami.knowsbeauty.com` (Dynadot DNS → DO server)
- **Dev/staging domain**: `miami.knowsbeauty.ai.devintensive.com`
- **Preview mode**: ON — only allowed emails (@expertly.com, @webintensive.com, aggiewaggie06@gmail.com, karissa.ostoski@gmail.com) can access the site; turn off to launch publicly
- **Stripe billing**: fully live — checkout and webhook processing both active as of 2026-06-11
- **Directory size**: 64 beauty businesses (miami.knowsbeauty.com), 48 wellness (miami.knowswellness.com), 49 health — 161 total across all verticals (as of 2026-06-12)
- **Featured subscription**: $29/month through Stripe Checkout; the Founding Partner concept was removed entirely
- **Second vertical**: miami.knowswellness.com is live in the database behind the preview gate; ready to open alongside beauty
- **Marketing AI**: Instagram caption and ad copy generators are **live and verified working on production** (both endpoints returned real generated content on 2026-06-19). The feature is turned ON by a database site-setting (`site_settings.marketing_ai_enabled = true`), set from the admin settings page; this database value takes precedence over the `MARKETING_AI_ENABLED` env var. As a belt-and-suspenders backup, the production server's `.env` also has both `MARKETING_AI_ENABLED=true` and `MARKETING_AI_ENABLED_PROD=true`, so the feature stays on even if the database value were ever removed. LLM calls route through the centralized Expertly AI gateway (no Anthropic key on the server). See `operations.md` → Feature Flags for the full mechanism, and `stories.md` for the launch-readiness risk note.

## GitHub

Repo: `david-wi/known-around-town` — private repo on GitHub.
Container image: `ghcr.io/david-wi/known-around-town:latest`

## Operator

David Bodnick (`david@bodnick.com` / `david@expertly.com`). AI Product Manager: Posey (Slack: `#agent-posey-knows-beauty` in expertlyhq workspace).
