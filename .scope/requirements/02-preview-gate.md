# Epic: Preview Gate — private beta access control

### KAT-020 — Preview gate middleware · V1 · implemented
**Persona:** David (operator).
When `PREVIEW_MODE_ENABLED=true`, a FastAPI middleware intercepts every request.
Unauthenticated visitors are redirected to `/preview-login`. Authenticated visitors
(valid `preview_token` cookie) pass through. Routes bypassed: `/health`,
`/api/v1/billing/webhook`, `/preview-login`, `/assets/`, `/media/`.
**Acceptance:** Given `PREVIEW_MODE_ENABLED=true` and no session cookie, when any
page is requested, then the response is a redirect to `/preview-login`; given a
valid cookie, then the requested page is served normally.

### KAT-021 — Email + 6-digit code authentication · V1 · implemented
**Persona:** Allowed preview user.
Visitors enter their email on `/preview-login`. If the email is on the allowed list,
a 6-digit code is sent via Resend. The visitor enters the code; if correct, a
30-day `preview_token` cookie is set. Disallowed emails receive the same
"check your email" response (no information leak about the allowed list).
**Acceptance:** Given an allowed email, when the visitor completes the code flow,
then they receive a `preview_token` cookie and are redirected to the requested page;
given a non-allowed email, when the visitor submits it, then they see "check your
email" but no code is sent and no cookie is set.

### KAT-022 — Preview session storage (MongoDB) · V1 · implemented
**Persona:** David (operator).
OTP codes are stored in `preview_codes` (TTL 15 minutes). Validated sessions are
stored in `preview_sessions` (TTL 30 days). Both collections are cleaned up automatically
via MongoDB TTL indexes.
**Acceptance:** Given a 6-digit code issued 16 minutes ago, when the visitor tries
to use it, then it is rejected; given a session cookie from 31 days ago, then the
visitor is redirected to `/preview-login`.

### KAT-024 — Admin API key bypasses preview gate · V1 · implemented
**Persona:** David (operator), Posey (PM agent).
When the preview gate is active, HTTP requests that include a valid `X-API-Key`
header matching `ADMIN_API_KEY` pass through the gate without a `preview_token`
cookie. This allows admin tooling and scripts to call any API endpoint from
outside a browser session.
**Acceptance:** Given `PREVIEW_MODE_ENABLED=true` and a request with a valid
`X-API-Key` header to any protected endpoint, when the request is received, then
it is not redirected to `/preview-login` and proceeds to route-level auth;
given an invalid or missing key, then the gate redirect applies as normal.

### KAT-025 — Owner portal bypasses preview gate · V1 · implemented
**Persona:** Salon owner (verified claim).
After their claim is verified, a salon owner receives a login link by email pointing to
`/owners/login`. They have no preview account. The preview gate must not intercept their
login or dashboard session — including any `fetch()` calls the dashboard pages make to
backend API endpoints.
Bypassed paths:
- `/owners` (the claim form page — exact), `/owners/login` (sign-in page), `/owners/me`
  (dashboard — has its own session check)
- `/api/v1/owner/` (all owner API endpoints: OTP login/verify, profile, stats, photos,
  logout, inquiries; each enforces owner-session auth at the route level)
- `/api/v1/claims` and `/api/v1/owner-leads` (claim form and email capture submissions
  from /owners — no preview account, no owner session)
- `/api/v1/billing/` (Stripe webhook + owner checkout + portal; billing routes enforce
  owner-session auth except the webhook which is machine-to-machine)
- `/api/v1/marketing-ai/` (AI features on owner dashboard; enforce owner-session auth)
**Acceptance:** Given `PREVIEW_MODE_ENABLED=true` and a salon owner who received a
verified-claim email with a login link, when they click the link, then they reach
`/owners/login` without being redirected to `/preview-login`; given a valid owner
session cookie, when they navigate to `/owners/me`, then they see their dashboard
without a preview-gate redirect; given no owner session cookie, when they navigate to
`/owners/me`, then the route itself redirects them to `/owners/login` (not the preview
gate); given an authenticated owner on the dashboard, when the page fetches their
profile, stats, photos, or billing status, then each API call succeeds (not a 302
redirect); given an anonymous salon owner who fills in the claim form and submits it,
then the claim is received by the server (not swallowed by a preview-gate redirect).

### KAT-026 — Search engine crawlers bypass preview gate · V1 · implemented
**Persona:** David (operator), Google/search crawlers.
`/robots.txt` and `/sitemap.xml` bypass the preview gate so search engine crawlers
receive correct crawl signals even while the site is in private preview. During
preview mode the `robots.txt` handler returns `Disallow: /` (signal: site is
private, do not crawl) and the `sitemap.xml` handler returns an empty urlset (no
business names enumerable before launch). When `PREVIEW_MODE_ENABLED=false` both
handlers automatically return their full live-site responses — no code change needed
at launch.
**Acceptance:** Given `PREVIEW_MODE_ENABLED=true`, when a request is made to
`/robots.txt`, then the response is HTTP 200 with `User-agent: *` and `Disallow: /`;
given a request to `/sitemap.xml`, then the response is HTTP 200 with a valid but
empty XML urlset; given `PREVIEW_MODE_ENABLED=false`, when a request is made to
`/robots.txt`, then the response includes `Allow: /` with the sitemap URL; given a
request to `/sitemap.xml`, then the response includes all published business URLs.

### KAT-023 — Public launch toggle · V1 · implemented
**Persona:** David (operator).
Setting `PREVIEW_MODE_ENABLED=false` in `/opt/known-around-town/.env` and
restarting the container disables the gate entirely. No code deploy is needed.
**Acceptance:** Given `PREVIEW_MODE_ENABLED=false` in production `.env`, when the
container is restarted, then unauthenticated visitors can access all public pages
without any redirect.
