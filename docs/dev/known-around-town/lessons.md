# known-around-town — Lessons Learned

## `to_doc()` must use `exclude_none=True` — sparse-unique indexes and null slots

`_crud.py`'s `to_doc()` helper converts a Pydantic model to a MongoDB document.
Before PR #159 it called `model.model_dump(by_alias=True)` without `exclude_none=True`,
so every Optional field that wasn't set was written to the document as explicit `null`.

This silently consumed the one "null slot" that MongoDB's sparse-unique indexes allow.
For example, `stripe_customer_id_1` is sparse+unique — documents **without** the field
are excluded from the index, but documents **with the field set to null** are included
and count as one duplicate of each other. The second new business added after the
security-incident restore always failed with `DuplicateKeyError: stripe_customer_id_1
dup key: null`, because the first new business had already consumed the one null slot.

**Fix:** `model.model_dump(by_alias=True, exclude_none=True)`. Optional fields that
aren't set are now absent from the document rather than present-and-null.

**Regression test:** `test_new_business_omits_unset_optional_fields` in
`tests/test_claim_pay_models.py`.

**Symptom to watch for:** Any `DuplicateKeyError` on `_1 dup key: null` is this bug
recurring — check `to_doc()` callers.

## Address field names: two conventions in the same codebase

The `Address` Pydantic model (`models.py`) uses `state` and `postal_code`.
But Jinja2 templates and some admin/test code sometimes reference `region` and `postal`
(legacy dict-key names from early seed scripts). When reading address fields in
templates, always check BOTH names:

```jinja2
{%- set _addr_region = business.address.state or business.address.region %}
{%- set _addr_postal = business.address.postal_code or business.address.postal %}
```

**Why this matters:** The JSON-LD template was checking `address.region` and
`address.postal` — which never existed in any seeded record — so Google never
received the state or zip code in structured data even though the data existed
as `address.state`. Fixed in PR #114.

## Seed data stores full address as one combined street string

The Miami seed (`seed/seed_miami.py`) stores the complete address in
`address.street` as a single string like "276 NW 26th St, Miami, FL 33127".
Separate fields (`postal_code`, `state`) are seeded as bare city/state stubs.
This means `postalCode` in structured data won't appear until records are
manually updated with parsed address components.

## GPS coordinates: model supports them, no data yet

`Address.lat` / `Address.lng` fields exist in the model and the JSON-LD template
now emits a `geo` block when they're present. But no seeded or imported business
currently has coordinates. To enable geo ranking benefits, coordinates need to
be added to business records (e.g., via Google Maps geocoding at import time).

## JSON-LD is in business.html head_extra block

The LocalBusiness and BreadcrumbList JSON-LD blocks live in
`backend/app/templates/business.html` inside `{% block head_extra %}`.
The template also already has: type inference (HairSalon/NailSalon/DaySpa/BeautySalon),
openingHoursSpecification, sameAs, image, @id.

## GridFS patch path in tests: patch at the point of use, not the definition

`app.routes.api.v1.owner_photos` and `app.routes.public.media` both do
`from app.database import get_gridfs_bucket`, which binds the function into
each module's own namespace. Patching `app.database.get_gridfs_bucket` has
no effect on those already-bound names. Always patch at the module that uses it:

```python
_PATCH_OWNER = "app.routes.api.v1.owner_photos.get_gridfs_bucket"
_PATCH_MEDIA  = "app.routes.public.media.get_gridfs_bucket"
```

This is the same principle that applies to any `from X import Y` import
across the codebase — patch `module_that_calls_it.Y`, not `X.Y`.

## Hero-photo promotion on delete: always check which photo was deleted first

The delete endpoint tracks whether the deleted photo was the hero *before*
computing the remaining list. Only then does it promote `remaining[0]` to hero.
Checking after the fact (or skipping the check) will incorrectly reassign the
hero on every delete, even when a non-hero photo is removed.

## Preview gate: use exact-path bypass when sub-paths must stay gated

The preview gate `_BYPASS_PREFIXES` tuple uses `startswith()` matching — any path that
begins with a listed prefix passes through. For paths where you want to open the path
itself but keep sub-paths gated, use `_BYPASS_EXACT` (a `frozenset`) instead:

```python
# WRONG for /owners — also bypasses /owners/login, /owners/me
_BYPASS_PREFIXES = (..., "/owners")

# RIGHT — only /owners itself is open; /owners/login stays gated
_BYPASS_EXACT = frozenset({"/owners"})
```

Note: `request.url.path` does NOT include query parameters. So `/owners?slug=salon`
has a path of `/owners` and is matched by the exact entry — no special casing needed.

Introduced in PR #150 when the claim form (`/owners?slug=<slug>`) needed to bypass
the preview gate for external salon owners clicking outreach email links, while
`/owners/login` (the authenticated owner dashboard sign-in) needed to stay gated.

## Only CI workflow (no separate deploy workflow)

The repo has one GitHub Actions workflow: `.github/workflows/ci.yml`. As of PR #115
it runs the whole `tests/` directory (it previously ran only `test_smoke.py`, which
meant the safety-guard tests never ran in CI). Deployment happens via a separate
mechanism on the server (`scripts/deploy.sh`, triggered by an auto-deploy webhook on
push to main / stage).

## The seed scripts are a "reset" — they DELETE, and they run against production on deploy

`backend/seed/seed_miami.py` is not an additive seed: `seed_network()` calls
`db.neighborhoods.delete_many`, `db.categories.delete_many`, and
`db.businesses.delete_many` to wipe stale records so the catalog matches the
curated reference. **`scripts/deploy.sh` runs `seed_networks` + `seed_miami`
against the PRODUCTION cloud database on every push to main** (`SEED_AFTER_DEPLOY=true`).

So the seed IS the demo-data reset, and it legitimately touches production. That is
why production data was once wiped — someone ran the same seed pointed at the live
database by hand.

**Guardrail (PR #115):** `seed/_helpers.assert_seed_target_allowed()` is called at
the top of both `main()` entrypoints before any DB access. It allows the seed only
for a confirmed-local/dev target (`ALLOW_LOCAL_MONGODB=true` AND a local host) or the
in-memory test database, OR when `KAT_ALLOW_PRODUCTION_RESET=true` is set on purpose
(the deploy script sets it via `docker compose exec -e`). Everything else — the cloud
database, an unknown host, an empty URL — fails closed and aborts. If you ever need to
re-seed production by hand, you must set `KAT_ALLOW_PRODUCTION_RESET=true` deliberately;
that requirement is the safety net, do not remove it. `backfill_founding_partners.py`
is intentionally NOT guarded (it only `update_many`s a flag, deletes nothing, and is
run against production by design).

## Traefik TLS cert CN mismatch when mixing .com and dev domains in one router (2026-06-12)

**Symptom:** New `.com` hostnames were routing correctly but serving a TLS cert with a dev subdomain CN (e.g., `CN=miami.knowswellness.ai.devintensive.com` for a request to `miami.knowswellness.com`). Browsers didn't error because the `.com` domain appeared as a SAN on the cert — but it's architecturally wrong.

**Root cause:** Traefik's certResolver generates one cert per router and uses the **first `Host()` entry** as the cert's main domain (CN). The old routers listed dev subdomains first, so the dev subdomain became the CN even for certs that also covered `.com` domains.

**Fix (PR #163):** Split each vertical into two routers — `kat-<network>-com` (public `.com` domains only) and `kat-<network>-dev` (dev subdomains only). Each gets its own cert with the correct CN for its audience.

**Apply compose file changes:** Watchtower only applies image changes automatically. After editing `docker-compose.prod.yml`, you must restart the backend manually: `docker compose -f docker-compose.prod.yml up -d --no-deps backend`. Traefik picks up the new router labels within seconds. If Traefik still serves stale certs after a backend restart, try `docker restart traefik`.

**Cert in acme.json but wrong cert served:** Even when the correct cert is in `/opt/traefik/acme.json`, Traefik may serve an older cert that also covers the requested hostname (via SAN). A `docker restart traefik` usually forces re-evaluation of cert-to-router assignments.

## Preview gate — bypass the PAGES and ALL API CALLS for any owner journey (2026-06-12)

This pattern burned us twice in the same session. The principle: when you add a
page to the preview gate bypass list, **immediately grep that page's template for
every `fetch(` call and add those API endpoints to the bypass list too**. A page
that loads fine but whose form submissions hit blocked API endpoints fails
completely and silently — the browser gets an HTML redirect instead of JSON,
shows no error, and the form just does nothing.

**Round 1 (PR #155):** Added the claim form page (`/owners`), the login page
(`/owners/login`), and the dashboard (`/owners/me`). Also added the OTP API
(`/api/v1/owner/login/`) — but that was the only API endpoint added.

**Round 2 (PR #156):** Discovered the claim form submission, email lead capture,
and the entire authenticated owner dashboard (profile, stats, photos, billing,
AI tools) were all still blocked. An owner who logged in successfully could not
do anything in their dashboard; a new owner submitting the claim form got a silent
failure.

**Complete bypass list after PR #156:**
- Pages: `/owners`, `/owners/login`, `/owners/me`
- APIs: `/api/v1/owner/` (all owner endpoints), `/api/v1/billing/` (webhook +
  checkout + portal), `/api/v1/claims`, `/api/v1/owner-leads`,
  `/api/v1/marketing-ai/`

**Rule for the future:** For every page added to `_BYPASS_EXACT` or
`_BYPASS_PREFIXES`, run `grep -n "fetch(" backend/app/templates/<page>.html`
and verify each target URL is also on the bypass list before merging. If the
API endpoint enforces its own owner-session auth at the route level, bypassing
the preview gate for it is safe — "bypassed" means skip the preview-cookie check,
not skip all auth.

**Also discovered (2026-06-12):** `miami.knowsbeauty.com` DNS had split-brain —
one Dynadot nameserver (ns1) had the correct A record, the other (ns2) still
served the old parking address. Fixed by re-calling `set_dns2` via the Dynadot
API; both nameservers synced within ~60 seconds. TTL is 300s so resolvers clear
within 5 minutes. If the site ever seems intermittently unreachable, check both
nameservers: `dig +short miami.knowsbeauty.com @ns1.dyna-ns.net` and
`@ns2.dyna-ns.net`.

## Preview login: allow-list is silent, sessionStorage preserves state (2026-06-12)

**Symptom:** "I got a code but there's no place to enter it." — David, bug report.

**Two bugs in one report:**

1. **Silent allow-list miss.** `preview_auth.is_allowed_email()` returns `True` only for
   `@expertly.com`, `@webintensive.com`, and a short explicit list. The API endpoint
   (`/api/v1/preview/login/request`) intentionally returns `{"ok": true}` regardless of
   whether an email is on the list — this prevents probing which addresses are allowed.
   The JS shows the code-entry step on success, so the user sees "check your email" but
   receives nothing. Fix: add the missing email to `ALLOWED_EMAILS` in `preview_auth.py`.

2. **JS state lost on navigation.** The code-entry step is shown by JavaScript after
   the email form succeeds. All state is in-memory — if the user navigates away (to
   their email app) and comes back, the page resets to step 1 and the code field
   disappears. The user has a valid code they can't enter.
   Fix: save the email in `sessionStorage` when the code step is shown; restore it on
   page load. Clear on successful verify or "use a different email". Uses a try/catch
   around all sessionStorage calls for private-browsing resilience.

**Rule:** Any time you add a new preview login UI step that requires round-trips to
other apps (email, SMS), save the UI state in sessionStorage so it survives app-switch.
Consider this the "browser-back from email app" test.

## Preview gate bypass: _BYPASS_EXACT vs _BYPASS_PREFIXES

`preview_gate.py` has two bypass mechanisms:
- `_BYPASS_PREFIXES` — tuple checked with `str.startswith()`; for path families like `/assets/`, `/api/v1/owner/` where all sub-paths should also bypass
- `_BYPASS_EXACT` — frozenset of exact paths; for single paths like `/robots.txt` where no sub-paths should bypass

Single-path entries belong in `_BYPASS_EXACT`. Using `_BYPASS_PREFIXES` for `/robots.txt` would also bypass `/robots.txt.bak`, `/robots.txt/anything`, etc. — correct semantics require the frozenset.

**Handlers that are bypassed must check preview mode themselves.** The gate short-circuits before the handler runs, so if the handler should behave differently during preview it must call `get_settings().preview_mode_enabled` directly. For `robots.txt` and `sitemap.xml`: return a "site is private" signal during preview (Disallow: /, empty urlset), and the full live-site response once preview is off.

**Handler order matters.** Any preview-mode short-circuit in a handler must come BEFORE the `_require_tenant()` call.

## Production feature flags use `_PROD` suffix — staging does not (2026-06-12)

`docker-compose.prod.yml` passes two different environment variables for `MARKETING_AI_ENABLED`:
- **Staging**: reads `${MARKETING_AI_ENABLED:-true}` — defaults to on so staging always has AI
- **Production**: reads `${MARKETING_AI_ENABLED_PROD:-}` — defaults to empty/off

This split is intentional: staging always has AI on; production stays off until explicitly enabled with the `_PROD`-suffixed variable. Setting `MARKETING_AI_ENABLED=true` in the production `.env` silently does nothing.

**Rule**: When updating or checking any feature flag for production, verify against the `environment:` block in `docker-compose.prod.yml` to find the actual variable name the container reads. Don't assume staging and production read the same name.

## Never list a pricing feature that isn't built (2026-06-12)

The pricing page advertised "Google Business Profile sync — hours, photos, services" as a Featured tier benefit. That feature was never built — no code for it exists anywhere in the codebase. It was removed in PR #187 after discovery.

**How to catch this in future:** Before publishing any pricing copy, grep the codebase for the feature. If no routes, services, or models implement it, do not ship the copy.

**Related:** The `MARKETING_AI_ENABLED` feature flag was blank on production even though the AI caption and ad copy endpoints were built and advertised. Subscribers who paid $29/month would hit a 404. Always verify every feature flag that controls advertised functionality is actually enabled before launch. See the Feature Flags section in `operations.md`. `_require_tenant()` does a DB lookup and raises HTTP 404 for unknown hosts (like test client hosts), so putting the preview check after it causes test failures for handlers that have been bypassed. Put preview checks first so they work unconditionally.

## Business status values: "live" not "published" (2026-06-12)

`PublishStatus` enum (models.py) has three values: `"draft"`, `"live"`, `"archived"`. There is no `"published"`.

Any MongoDB query filtering for live businesses must use `{"status": "live"}`. Querying for `"published"` silently returns zero results — no error, just an empty count. The admin sync page (PR #194) originally used `"published"` and showed 0/165 salons until fixed.

**Regression test:** `test_sync_page_counts_live_businesses` in `tests/test_google_places.py` seeds live businesses and verifies the count is > 0. If it fails, a query is using the wrong status value.

## Live domain is miami.knowsbeauty.com (not miamiknowsbeauty.com) (2026-06-12)

The live public URL is `https://miami.knowsbeauty.com` — the Traefik router label and TLS cert both use this hostname. Sending curl or Playwright to `miamiknowsbeauty.com` or using `Host: miamiknowsbeauty.com` returns a 404 from Traefik because no router matches.

Admin routes (`/admin/*`) bypass the preview gate entirely — useful for verifying deployed admin UI without a preview session cookie. Public pages require either a `preview_token` cookie (from the preview login flow) or preview mode disabled.

## Tailwind pre-compiled CSS: peer-checked variants not available (2026-06-12)

`reference.css` is a pre-compiled Tailwind CSS file. It only contains utilities that
were present in templates at compilation time. When adding new templates, Tailwind
`peer-*` interactive variants (e.g. `peer-checked:bg-rose-500`, `peer-focus:ring-2`)
will NOT be available — they're not in the compiled file.

**Fix:** For toggles and other interactive elements in new templates, use one of:
1. **Inline styles** server-rendered from the template variable for the initial state:
   `style="background-color: {{ '#f43f5e' if enabled else '#d6d3d1' }}"`
2. **Small JS onchange handler** to update visual state on click
3. **Rebuild reference.css** by running the Tailwind CLI with the new template in scope

The settings page toggle (PR #191) uses inline styles + JS onchange as the simplest
approach that doesn't require a CSS rebuild.

## site_settings MongoDB collection: DB-first / env-var-fallback pattern (2026-06-12)

Feature flags that need to be toggled without a server restart are stored in the
`site_settings` collection (single document, `_id: "global"`). The pattern:

1. `get_site_setting(key, default=None)` — reads from DB, returns `default` if not set
2. `update_site_settings(updates: dict)` — upserts into the global doc
3. Each feature's "check" function reads DB first, falls back to the env var

This means: no DB value → env var behavior unchanged (safe default). Once the admin
toggles it, DB value takes effect immediately without restart. The toggle persists
across container restarts.

**Example:** `get_marketing_ai_enabled()` in `services/site_settings.py`:
- If `site_settings["marketing_ai_enabled"]` exists → use it
- Otherwise → call `ai_caption.feature_enabled()` (reads `MARKETING_AI_ENABLED` env var)

**HTML checkbox POST body gotcha:** Unchecked checkboxes send nothing in a POST body.
Never use `Form(...)` parameters for checkboxes — they'll be missing and FastAPI will
raise a 422. Always use `request.form()` and check `form.get("field") == "on"`.

## Bypassed handlers must use the same DB-backed helper as the rest of the app (2026-06-12)

When a route (like `robots.txt` or `sitemap.xml`) is in the preview gate's bypass list,
it runs outside the gate — so the gate's DB-backed preview check doesn't help it. If
the handler reads `get_settings().preview_mode_enabled` (env var) instead of
`await get_preview_mode_enabled()` (DB-backed), the admin toggle works for visitors
(gate opens) but the bypassed handler still sees the old env var value.

**Consequence:** David toggles the admin UI to open the site. Visitors can access pages.
But `robots.txt` still returns `Disallow: /` (env var says private) — Google thinks the
site is still private and won't index it.

**Rule:** Every handler that inspects `preview_mode_enabled` must call the DB-backed
`get_preview_mode_enabled()` helper, whether it's inside or outside the bypass list.
Caught in CODEREVIEW for PR #197 before it shipped.

## Multi-city Traefik routing — wildcard HostRegexp works better than explicit Host() lists (2026-06-13)

When adding a new city subdomain (e.g., `boca-raton.knowsbeauty.com`), the Traefik
router rule must include it. Rather than maintaining an ever-growing explicit list like
`Host(`miami.knowsbeauty.com`) || Host(`boca-raton.knowsbeauty.com`) || ...`, use:

```yaml
rule: "HostRegexp(`{subdomain:[a-z0-9-]+}.knowsbeauty.com`)"
```

This matches any subdomain automatically. The app already does city lookup from the
`Host` header, so no code change is needed per city — the router just needs to pass
the request through.

**Why not do this from day one:** Wildcard TLS certs require the DNS-01 ACME challenge
(Traefik needs Cloudflare/Dynadot API access), whereas explicit Host() rules use
HTTP-01 which works out of the box. For now we enumerate known cities until
DNS-01 is wired up. Add each new city's subdomain to the Traefik router rule in
`docker-compose.prod.yml`.

## PDF generation from Jinja2 templates — render locally, print with Playwright (2026-06-13)

The Owner Journey PDF is a static file committed to the repo. To regenerate it after
template changes:

1. Read the theme dict from `pages.py` (`_NETWORK_THEMES["beauty"]`)
2. Use Jinja2 directly (no FastAPI server needed) to render `walkthrough.html`
3. Strip `{% extends %}` / `{% block content %}` wrappers and embed CSS inline
4. Write standalone HTML to `/tmp/walkthrough_rendered.html`
5. Use Playwright `page.pdf(format='Letter', print_background=True)` to print it
6. Save to `backend/app/static/walkthrough/mkb-owner-journey.pdf` and commit

The key: set `print_background=True` otherwise Tailwind's background colors are stripped.
No margins needed at the PDF level since the template has its own padding.

## Static files are served under /assets/, not /static/ (2026-06-13)

`backend/app/static/` is mounted at the `/assets/` URL prefix in `main.py`. Any
code that references `/static/...` for this app's own static files will get a 404.

Affected areas:
- `preview_gate.py` bypass list: the Owner Journey PDF is at `/assets/walkthrough/`
  (not `/static/walkthrough/`). Fixed in PR #256.
- Any template or inline script that builds URLs to static files must use `/assets/`.

**How to verify:** The `StaticFiles` mount in `main.py` reads:
`app.mount("/assets", StaticFiles(directory="app/static"), name="static")`

## Search chips: onclick must traverse DOM to find the form (2026-06-13)

The home page search chips live *outside* the `<form>` closing tag (they're in a
following `<div>` inside the same `<section>`). `this.form` doesn't work.

The reliable pattern:
```html
onclick="var f=this.closest('section').querySelector('form');
         f.querySelector('input[name=q]').value=this.textContent.trim();f.submit();"
```

`this.closest('section')` walks up to the shared parent, then `.querySelector('form')`
finds the form. This survives any amount of intermediate `<div>` nesting.

## Dead dropdowns: remove before launch, don't try to wire (2026-06-13)

Category and neighborhood pages had Tier and Sort dropdowns with no `onchange`
handlers — selecting an option did nothing. The decision was to **remove** them
pre-launch rather than implement server-side filtering in a rush.

Rule: any `<select>` on a visitor-facing page must have a working `onchange` or a
form submission target. A `<select>` that changes nothing is worse than no filter at
all — it signals a broken directory to first-time visitors.

## Inquiry form contact validation: client-side only (2026-06-13)

`BusinessInquiry` model (`models.py`) has `email: Optional[str] = None` and
`phone: Optional[str] = None` — the API layer accepts submissions with neither.
The "at least one contact method" rule is enforced client-side in the form's
JavaScript submit handler.

If you ever need server-side enforcement, add a Pydantic `@model_validator(mode='after')`
to `BusinessInquiry` that raises a `ValueError` when both are None/empty.

## Playwright admin key bypass for preview-gated pages (2026-06-13)

All public pages are behind the preview gate. Playwright automation can bypass it
via the admin API key header:

```python
ctx = browser.new_context(
    extra_http_headers={"X-API-Key": ADMIN_KEY},
)
```

This works because the preview gate checks `X-API-Key` before the cookie check.
The key value is in the production `.env` as `ADMIN_API_KEY`.

## Inline HTML mockups for gated features (2026-06-13)

When a tool requires a real subscription/session to demo (e.g., Marketing AI needs
a Featured subscription), don't try to take screenshots with a test account. Instead,
build inline HTML mockups directly in the template using the same Tailwind classes
and design patterns as the real tool. They render identically in the browser and in
the PDF, look completely authentic, and let you control the example content to be
maximally compelling. Much faster and more reliable than any screenshot approach.

## Always add redirect routes for marketing-linked URLs (2026-06-14)

When a URL might appear in marketing materials (emails, social posts, ads), add a
301 redirect from the "obvious" path to the actual page even if the obvious path was
never officially announced. The redirect pattern in `pages.py` is:

```python
@router.get("/owners/claim", response_class=HTMLResponse)
async def owners_claim_redirect() -> RedirectResponse:
    return RedirectResponse(url="/owners#claim-form", status_code=301)
```

PR #259 caught `/owners/claim` returning 404. Any link in the wild would have
dead-ended there. Audit likely marketing paths early and add redirects defensively.

## Pricing page conversion: CTA placement matters (2026-06-14)

On the pricing page, the "Claim your listing" button was below 12 feature bullets —
completely off-screen at a standard 1440×900 viewport. Owners who didn't scroll never
saw a way to act. Add the primary CTA immediately after the price (before the feature
list). Keep a second CTA at the bottom for thorough readers. Two CTAs on a pricing
card is correct UX, not redundant.

## Home page og:image: pass it through the route context, don't add it manually in the template (2026-06-14)

`base.html` emits `og:image` only when the route passes `og_image` in the template
context (`{% if og_image %}<meta property="og:image"...>`). Every page route does this.
The home route was the only exception — it passed `hero_photo_url` but not `og_image`,
so `base.html` silently emitted nothing. Someone then added a manual `og:image` tag
inside `home.html`'s `head_extra` block as a workaround, producing TWO og:image tags
(one blank from `base.html`, one correct from `home.html`).

**Fix (PR #261):** Add `"og_image": city.get("hero_photo_url")` to the home route
context and remove the manual tag from `home.html`. Now all pages follow the same
pattern.

**Pattern to enforce:** never add `og:image` manually in a page template — always pass
`og_image` through the route context so `base.html` handles it.

## Sitemap lastmod: use the record's actual date, not today (2026-06-14)

Editorial guide entries in the sitemap previously used `today_str` (today's date) as
`<lastmod>`. Google's crawler therefore treated every guide as modified daily, wasting
crawl budget and reducing the signal value of our date fields.

**Fix (PR #261):** Use `g.get("updated_at") or g.get("published_at")` and fall back
to `today_str` only when neither field exists. Every guide now reports its real
publish date as `lastmod`.

**General rule:** never use today's date as a `lastmod` for content that doesn't
actually change daily — it signals noise to search engines and erodes the credibility
of your sitemap dates overall.

## Verifying preview-gated pages: mint a short-lived token via the container (2026-06-17)

To screenshot a public page while the site is still in preview mode, mint a
preview-session token, set the cookie via the set-session link, screenshot, then
delete the token. Two gotchas:

1. **The hashing helper is `app.services.preview_auth.hash_value`** (SHA-256 hex),
   not `app.security.tokens.hash_value`. A `preview_sessions` doc needs
   `{_id, email, token_hash, created_at, expires_at}`; `set-session` only checks
   `token_hash` + `expires_at > now`.
2. **Run the mint/delete script from `/app` inside the container with
   `PYTHONPATH=/app`** — `docker exec -w /app -e PYTHONPATH=/app
   known-around-town-backend-1 python <script>`. A script left in `/tmp` fails with
   `ModuleNotFoundError: No module named 'app'` because `/tmp` isn't on the path.

Recipe: `python` script reads `MONGODB_URL` + `MONGODB_DATABASE` (defaults
`who_knows_local`), inserts the session doc with a 30-minute `expires_at`, prints
the token. Then Playwright (Python, `channel='chrome'`, 1280×800) visits
`/api/v1/preview/set-session?token=...&next=/pricing`. Delete the token by `_id`
when done and confirm the set-session link returns 401. Used in PR #347 to verify
the pricing-copy reposition. The simpler admin-key header bypass
(`X-API-Key: ADMIN_API_KEY`) also works for read-only checks — see the Playwright
admin-key lesson above.

## Never advertise an enforced limit the code doesn't enforce (2026-06-17)

The pricing copy advertised "50 captions/month" and "20 ad campaigns/month" for the
AI tools, but `ai_caption.py` / `marketing_ai.py` enforce no monthly counter — only
a per-call output-token cap and a per-input character cap. Stating an enforced number
that isn't enforced is the same false-claim class as the "Google Business Profile
sync" feature that was never built (see the earlier lesson). PR #347 replaced the
numbers with "generous monthly usage included". Sibling rule to "Never list a pricing
feature that isn't built": before publishing any quantified plan limit, grep the code
for the counter that enforces it; if there's no counter, don't state a number.

## Owner-facing counts must match what the tool actually returns (2026-06-19)

The post-upgrade welcome email (`owner_email.py`, both the text and HTML
subscription-confirmed bodies) promised "20 ready-to-run ad variations", but the
ad-copy generator is hard-coded to return **exactly 3** — `ai_caption.py`
(`build_ad_copy_system_prompt` says "Return EXACTLY 3 variations") and
`marketing_ai.py` both describe 3, and so do the dashboard, pricing, owners, and
walkthrough pages. Only the welcome email was inflated, so a new owner's very first
use of the tool would deliver far less than the email led them to expect. Fixed in
PR #351 by aligning the email to "3". Same class as the "never advertise an enforced
limit" lesson: before stating a number in owner-facing copy, grep for the place that
produces it and match the copy to reality. The ad-copy count lives in the system
prompt, not a config value, so "make the product produce 20" would be a real
product-scope change, not a copy tweak — the correct least-invasive fix was the copy.

## Live profile checklist: server-rendered state needs a client-side update hook (2026-06-19)

The owner dashboard's "Complete your profile" checklist (`owner_me.html`) is
rendered server-side from `owner_business.photos` etc. at page load. The "Add a
photo" item stayed showing as not-done after an owner uploaded their first photo,
until they reloaded — the page contradicted the action they just took. Fix (PR #351):
render the photo row with BOTH a done and a not-done branch (`data-checklist-done` /
`data-checklist-todo`, toggled by the `hidden` class) plus id hooks
(`profile-checklist`, `checklist-count`, `checklist-progress`,
`data-checklist-total`), and have the existing `updateCountLabel()` photo handler call
a new `syncChecklistPhoto()` that flips the row and recomputes the "X of 5 complete"
count + progress bar live. The 4 static rows render only one branch and signal done
via a `.line-through` label, so the live count loop reads each row's visible state.
When the photo is the LAST incomplete item, the section is hidden once complete (it's
only server-rendered while something is incomplete, so leaving it up would show a
finished checklist still nagging). PR #352. Pattern: any checklist/progress UI that's
server-rendered from a value the page can also change client-side needs a matching
client-side updater, or it goes stale until reload.

## Encouraging empty states beat bare zeros (2026-06-19)

A freshly-upgraded owner's "Listing performance" panel showed bare "0 page views /
0 messages", which reads as "the directory is broken" rather than "tracking just
started". Fix (PR #351): added a short reassurance line under each metric ("Views
appear here as Miami shoppers find your listing." / "Messages from shoppers will show
up here once they reach out."), rendered hidden and revealed by the stats JS only when
the fetched count is exactly 0. No fabricated numbers — the zero stays visible. Sibling
to the "no fake limits" rule: never invent activity, but DO frame a legitimate zero
encouragingly.

## Auto-merge can fire on the first commit's green build before a follow-up lands (2026-06-19)

`gh pr merge --auto --squash` merges as soon as the required checks ("Smoke tests")
pass. If you push a SECOND commit to the branch a few minutes later (e.g. applying
code-review follow-ups), the first commit's build may already be green and auto-merge
fires immediately — squashing only the first commit and dropping the second. This
happened on PR #351: the second commit (two review fixes) never reached main; it had
to be re-shipped as PR #352. Guard: after pushing a follow-up commit to a PR that
already has `--auto` set, confirm the merge waited for the NEW head before treating it
as done — `gh pr view <n> --json mergedAt` plus a `git show origin/main:<file> | grep`
for a marker unique to the follow-up. If the merge already landed without it, open a
follow-up PR rather than assuming the squash caught everything.
