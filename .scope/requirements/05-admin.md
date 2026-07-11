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
The admin analytics page at `/admin/analytics` shows total businesses, total
inquiries, subscription metrics, and inquiry volume over time.
**Acceptance:** Given David at `/admin/analytics`, when the page loads, then
key metrics are displayed including total businesses, subscription metrics, and
inquiry counts; given a recent claim was submitted from an outreach-tagged link,
then the recent-claims list displays the saved claim source marker; given David
has prepared first-send outreach targets, then the dashboard displays their
current listing views, Miami Knows Beauty-referred views, action clicks, claim
state, and subscription state so David can spot the first conversion without a
database query.

### KAT-052 — Database seeding (production-guarded) · V1 · implemented
**Persona:** David (operator).
Seed scripts at `seed/seed_miami.py` and the city-specific seed modules populate
neighborhoods, categories, and business listings from Miami public data. Seeding
is destructive (wipes and recreates records) and is guarded by
`KAT_ALLOW_PRODUCTION_RESET=true`. Normal deploys do NOT run seeds.
**Acceptance:** Given `KAT_ALLOW_PRODUCTION_RESET` not set, when any destructive
seed entrypoint runs, then it exits with an error and does not modify production
data; given the flag set, then every checked-in source row for the selected city
is seeded; given an existing listing is being re-seeded from a checked-in source,
then source-owned editorial fields refresh while the existing listing keeps its
stable identity and live operational/owner state, including claim and payment
fields, paid Featured/Concierge Voice state, archived lifecycle, Google cache,
analytics counters, owner contact/social fields, services, hours, and owner-uploaded
photos. A repeated re-seed must not create duplicate listings or replace the
existing `_id`/`created_at`.
**Regression evidence:** The KAT-052 disposable canary covers the reviewed
13-row manifest (12 satellite rows plus one Miami control row) against mongomock
and proves source refresh, operational-field preservation, stable IDs, and zero
duplicates for the Miami, Aventura, Coral Gables, South Beach, and Sunny Isles
writers. A deploy-derived wiring inventory confirms that every business
replacement writer uses the same helper, and guard tests confirm every city
entrypoint fails closed before database access.
**Incidents:**
- 2026-07-11 — The Miami custom replacement path restored archived listings and
  dropped paid/voice/counter state because it replaced the whole document without
  a complete operational-field boundary.
- 2026-07-11 — The follow-up 13-row canary showed that the Miami fix did not reach
  the Aventura, Coral Gables, South Beach, and Sunny Isles replacement loops;
  eight satellite rows lost operational/owner state on re-seed. Source
  consolidation is held until those writers share the reviewed boundary.

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
