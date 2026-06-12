# known-around-town — Lessons Learned

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

## Preview gate bypass: _BYPASS_EXACT vs _BYPASS_PREFIXES

`preview_gate.py` has two bypass mechanisms:
- `_BYPASS_PREFIXES` — tuple checked with `str.startswith()`; for path families like `/assets/`, `/api/v1/owner/` where all sub-paths should also bypass
- `_BYPASS_EXACT` — frozenset of exact paths; for single paths like `/robots.txt` where no sub-paths should bypass

Single-path entries belong in `_BYPASS_EXACT`. Using `_BYPASS_PREFIXES` for `/robots.txt` would also bypass `/robots.txt.bak`, `/robots.txt/anything`, etc. — correct semantics require the frozenset.

**Handlers that are bypassed must check preview mode themselves.** The gate short-circuits before the handler runs, so if the handler should behave differently during preview it must call `get_settings().preview_mode_enabled` directly. For `robots.txt` and `sitemap.xml`: return a "site is private" signal during preview (Disallow: /, empty urlset), and the full live-site response once preview is off.

**Handler order matters.** Any preview-mode short-circuit in a handler must come BEFORE the `_require_tenant()` call. `_require_tenant()` does a DB lookup and raises HTTP 404 for unknown hosts (like test client hosts), so putting the preview check after it causes test failures for handlers that have been bypassed. Put preview checks first so they work unconditionally.
