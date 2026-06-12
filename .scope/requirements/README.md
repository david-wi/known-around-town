# Miami Knows Beauty — requirements (git-backed, Scope-style)

This folder is the source of truth for Miami Knows Beauty (Known Around Town platform)
requirements. One Markdown file per epic. Each requirement has a stable ID (`KAT-###`),
a **tier**, a **status**, the **persona** it serves, a plain description, and acceptance criteria.

## Tiers

- **V1** — part of the initial live product.
- **V2** — next-phase expansion (multi-city, vertical domains, advanced features).

## Status vocabulary

`draft` → `definition` → `ready_to_build` → `implemented` → `needs_fix`.

Requirements stay below `implemented` until each one has functional code, wiring,
tests, and fresh evidence (CI pass, visual verification, or Playwright screenshot).

## Epics

| File | Epic |
|------|------|
| `00-foundation.md` | Platform infrastructure, Docker, CI, multi-tenant routing |
| `01-public-directory.md` | Neighborhood/category browsing, business pages, SEO |
| `02-preview-gate.md` | Preview mode: email + code auth for private beta |
| `03-owner-portal.md` | Owner login, dashboard, profile editing, photo management |
| `04-billing.md` | Stripe Checkout, webhooks, Founding Partner badge |
| `05-admin.md` | Admin claims management, analytics, data seeding |
| `06-roadmap.md` | Upcoming features in planning or blocked states |

## Note on Scope binding

These files follow the Scope-style layout. The product is **not yet formally bound**
to Expertly Define via Scope tooling. Posey maintains these files by hand as part of
the standing instruction: every code change updates both `.scope/` and `docs/dev/`.

Product manager: Posey (Slack: `#agent-posey-knows-beauty` in expertlyhq workspace).
