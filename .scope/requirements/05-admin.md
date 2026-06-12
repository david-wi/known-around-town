# Epic: Admin — claims management, analytics, data seeding

### KAT-050 — Claims management panel · V1 · implemented
**Persona:** David (operator).
The admin panel at `/admin/claims` lists all pending ownership claim submissions
with name, email, phone, message, and the claimed business. David can approve or
reject claims. Approved claims update `claim_status` on the business document.
**Acceptance:** Given a pending claim, when David views `/admin/claims`, then the
claim appears with all submitted details; when David approves it, then the business
`claim_status` is updated to `claimed` and the owner can log in.

### KAT-051 — Analytics dashboard · V1 · implemented
**Persona:** David (operator).
The admin analytics page at `/admin/analytics` shows: total businesses, total
inquiries, Founding Partner count, and inquiry volume over time.
**Acceptance:** Given David at `/admin/analytics`, when the page loads, then
key metrics are displayed including total businesses (147), Founding Partner count,
and inquiry counts.

### KAT-052 — Database seeding (production-guarded) · V1 · implemented
**Persona:** David (operator).
Seed scripts at `seed/seed_miami.py` populate neighborhoods, categories, and
business listings from Miami public data. Seeding is destructive (wipes and
recreates records) and is guarded by `KAT_ALLOW_PRODUCTION_RESET=true`.
Normal deploys do NOT run seeds.
**Acceptance:** Given `KAT_ALLOW_PRODUCTION_RESET` not set, when the seed script
runs, then it exits with an error and does not modify production data; given the
flag set, then 147 businesses are seeded.

### KAT-054 — Admin settings page · V1 · implemented
**Persona:** David (operator), Posey.
A web interface at `/admin/settings` where David or Posey can toggle feature flags
and manage site-wide settings without SSH or command-line access.
Settings are stored in a `site_settings` MongoDB collection and take precedence
over environment variables so changes take effect instantly without a container restart.

Controls (as of PR #191, PR #197):
- **Marketing AI tools** — enables/disables the AI caption and ad copy generators
- **Site is private (preview mode)** — when on, only preview invitees can access the site; the status badge shows amber (private) or green (live). Turning it off is the launch action. robots.txt and sitemap.xml also update automatically so Google gets the correct crawl signal.
- **Google Search Console verification** — paste the Google-provided code; the HTML meta tag appears on every page immediately.

**Acceptance:** Given David at `/admin/settings`, when he changes any setting and saves, then the change takes effect immediately for all new requests (no restart needed); settings persist across container restarts.

### KAT-053 — Admin API key authentication · V1 · implemented
**Persona:** David (operator), Posey.
Write endpoints (`POST`, `PATCH`, `DELETE` on business resources) require an
`Authorization: Bearer {ADMIN_API_KEY}` header. Read endpoints are public.
**Acceptance:** Given a write request without the admin key, when the endpoint is
called, then it returns 401; given a valid key, then the operation succeeds.
