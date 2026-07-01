# known-around-town — Lessons Learned

## Public form rate limits must reserve atomically before side effects (2026-07-01)

For unauthenticated forms that create records or send email, do not rate-limit by
`count_documents(...)` on accepted rows and then insert. Parallel requests can all
observe the same pre-insert count and proceed, creating exactly the flood the
limit is meant to stop. Use an atomic reservation bucket before any route side
effect, and regression-test it with concurrent calls plus assertions that blocked
requests do not insert rows or send notifications.

Proxy IP handling matters here. Production runs behind Traefik while Uvicorn is
configured to trust forwarded headers; an attacker-controlled leftmost
`X-Forwarded-For` value can bypass an IP bucket if the limiter trusts it blindly.
For this app's current proxy shape, the limiter reads the rightmost forwarded IP
that Traefik appends and falls back to `request.client.host` only when the header
is absent.

## Copy-block lookups were the home/listing TTFB culprit — batch them with a per-request prime (2026-06-30)

The editable-wording system (`backend/app/services/copy.py`) resolved each snippet with one
sequential `copy_blocks.find_one` walking the most-specific→least scope cascade
(business → category → neighborhood → city → network → global). Home renders ~46 snippets; the
salon-listing page ~72, and its `business.*` keys are never seeded so each missed through all four
scope levels = 4 round-trips each. At ~10ms per serialized Atlas round-trip that was the ~0.9s gap
between home/listing (~1.5s) and pricing/owners (~0.57s). **Indexes were fine — the problem was the
COUNT of sequential round-trips, not their individual cost.**

Fix (PR #452): added `CopyResolver.prime(*, category_slug=, business_id=, neighborhood_slug=)` that
builds the page's full scope set (reusing `_scope_keys`), runs ONE `find` over the `$or` of those
scope_refs (+ locale), and caches rows keyed by `(scope_type, frozenset(scope_ref.items()), key)`.
`.get`/`get_copy` resolve from that cache when primed — same cascade order, same active-window check
(factored into one shared `_is_active` so the two paths can't drift), same `_format`, same
DEFAULTS→None fall-through — and fall back to the original per-key `find_one` for any scope dimension
that wasn't primed (so correctness is never traded for speed). Every public-page resolver primes once.

Gotchas worth remembering:
- **mongomock strips tzinfo on read; production Motor uses `tz_aware=True`.** The copy code computes
  a tz-aware `now` and compares it to the stored `active_from`/`active_until`. Under bare mongomock
  that comparison raises "can't compare offset-naive and offset-aware" in BOTH paths. The test
  (`backend/tests/test_copy_batching.py`) wraps the mock DB to re-attach UTC on reads so the test
  environment matches production.
- **mongomock returns a NEW collection wrapper object on every `db.copy_blocks` access**, so
  monkeypatching `find`/`find_one` on one access doesn't stick. Count queries at a stable proxy layer
  the code calls through, not by patching the mongomock collection.
- The home page builds two resolvers (its own + the shared base/footer context), so it primes the same
  base scopes twice = 2 queries. Still dozens→2; folding them is a base-context refactor left as a
  follow-up.

## WCAG AA color-contrast: nudge shades within the palette + test the *real* ratio (2026-06-30)

`frontend.md` mandates WCAG AA (4.5:1 for normal text). An axe-core audit found contrast was the only
violation type, in faint grey/gold text: stone-400 on white (~2.5:1), stone-500 on the dark footer
(~4.1:1), amber-600 on white (3.1:1), and — on the network landing — text dimmed below AA by a parent
`opacity-70` "coming soon" card. The fix pattern that worked: **move each shade one step within the
existing Tailwind palette so it crosses 4.5:1, without changing the design.** On white, darken
(stone-400→500 ~4.8:1, amber-600→700 ~4.9:1); on the dark footer, *lighten* (stone-500→400 ~7.8:1);
under an intentional opacity fade, darken enough to pass *through* the fade (stone-700/500→800 ~5.7:1 at
op-70) so the faded look is preserved. Both shades must already exist elsewhere in the compiled CSS or
Tailwind purge drops them.

**Test it behaviorally, not by string-match.** `backend/tests/test_a11y_contrast.py` reads each element's
*actual* shade from the template, maps it to its hex, and computes the real WCAG ratio (and models the
opacity-70 blend for the faded card). A future edit that re-lightens any of these text bits fails CI.
PRs #448/#449/#450 took the site from 52 contrast violations to 0 across all 8 page types. Reusable live
audit script: `Spaces/posey/tools/a11y/axe_contrast.py`. Watch out: a full axe run via CDN injection can
false-positive on document-title/html-has-lang/landmark — verify those against the curl'd HTML (the pages
do have `<html lang>`, `<title>`, one `<h1>`, `<main>`).

## Deploy verification: Watchtower can serve stale/reverted content mid-cycle — re-verify AFTER it settles (2026-06-30)

Deploy is GH Actions → push `:latest` to GHCR → **Watchtower** (300s poll, `WATCHTOWER_CLEANUP=true`)
pulls + restarts the container. There is **no CDN** (`server: uvicorn`). During the poll cycle the live
site can briefly run the new image, then be observed back on an OLDER image before it stabilizes (same
class that bit PR #434). Real case: after merging the a11y fix, an early audit read "0 violations", then
minutes later cache-busted curls consistently returned the OLD content on home+listing, until the
container restarted (`Up <n>s`) on Watchtower's cycle and stably applied the new image.

**Rule:** don't trust a single early post-merge check. Poll a unique deploy marker until present, then
re-confirm it's STILL present a minute later (guards a revert). When unsure, check the box:
`ssh -p 2222 root@174.138.81.31` → `docker ps --filter name=known` (a very recent `Up` = a cycle just
ran) and confirm live HTML matches `git main`. To force immediately: `ssh ... 'bash
/opt/known-around-town/scripts/deploy.sh'`. Host: miami.knowsbeauty.com → **174.138.81.31** (per
docs/deploy.md; the cheatsheet's 152.42.152.243 did not serve the site on 2026-06-30 — prefer .31).


## Features are disabled by HIDING, not deleting — don't "re-add" a deliberately-hidden one (2026-06-30)

This codebase disables an unfinished/not-yet-ready feature by **hiding its HTML while leaving the
supporting JavaScript in place (guarded with `if (element) {...}` so it's a safe no-op)**, marked with a
Jinja comment like `{# Listing performance is deliberately hidden pre-launch. #}`. The guarded JS is
NOT dead code to clean up — it's scaffolding kept ready so the feature can be cleanly re-enabled later.

Concrete case: the owner dashboard's "Listing performance" panel (page views + taps to call / website /
directions — the `/api/v1/owner/stats` data) LOOKS like a wiring gap: the endpoint is registered and
returns real counters, but `owner_me.html` doesn't render them, and the inquiries JS references
now-absent `stat-inquiries` elements. It is NOT a gap — commit `0343193` ("Fix owner QA copy and listing
trust gaps") **deliberately hid the panel pre-launch** because a freshly-upgraded owner would see 0 views
/ 0 messages, which looks bad. The preview dashboard (`owner_dashboard.html`, route `/owner/dashboard`)
still shows the panel with SAMPLE numbers; the real authed dashboard (`owner_me.html`) hides it.

**Rule: before "fixing" an apparently-unwired UI feature here, check git history (`git log -S` on the
element/marker).** If it was deliberately hidden, do NOT re-add it — you'd revert an intentional product
decision. POST-LAUNCH follow-up (gated on real traffic + David): un-hide the performance panel so paying
owners see their ROI — the data pipeline + endpoint already exist; it's the strongest renewal argument.

## Step markers for the stop-compliance hook must be EXACTLY `PREFIX-N/TOTAL:` (2026-06-30)

The `stop-compliance-check.py` hook matches procedure step markers with the regex `PREFIX-N/TOTAL:` —
the colon must come **immediately after the total number**. Writing the step NAME before the colon
(`CHANGE-3/16 (Plan):`) does NOT match, so the hook can't see your progress and re-fires
"in the middle of CHANGE workflow" indefinitely — even when you've finished or correctly abandoned the
procedure. A CHANGE correctly abandoned at the investigation gate is closed by emitting the remaining
markers in exact format (`CHANGE-3/16:` … `CHANGE-16/16:`, each N/A with brief evidence). Verify with the
hook's own `find_incomplete_procedure()` if stuck.

## Public business API must hide archived cities and archived listings (2026-06-30)

The public JSON endpoints under `/api/v1/businesses` are unauthenticated shopper
surfaces, not admin export endpoints. They must follow the same visibility rule
as public pages: only live businesses in non-archived cities are visible.

Bug found during the Hollywood duplicate cleanup: after archiving the duplicate
`hollywood-fl` city, `hollywood-fl.knowsbeauty.com` no longer rendered pages, but
`GET /api/v1/businesses?city_id=hollywood-fl&status=live` still returned 17 live
duplicate businesses and `GET /api/v1/businesses/by-slug/hollywood-fl/<slug>`
returned those rows by JSON. Root cause: the API read directly by `city_id` /
`slug` / `_id` without checking the parent city status and without forcing
`status: live` on public reads.

Fix: public list/detail/by-slug business API reads now require a non-archived
city and a live business. Requests for archived cities return an empty list for
collection reads and 404 for detail reads. Regression coverage:
`tests/test_businesses_api_visibility.py`.

## Business claim status uses `verified`, even when admin UI says approved (2026-06-28)

The claim verification endpoint writes successful reviews as `business_claims.status = "verified"` and
`businesses.claim_status = "verified"`. The admin analytics page uses the owner-friendly label "approved",
but its query must count `status: "verified"`, not `status: "approved"`.

Symptom: after David verifies the first real salon claim, `/admin/claims` removes the pending row and the
business is verified, but `/admin/analytics` still shows `0 approved`. Regression coverage lives in
`tests/test_admin_analytics.py::test_analytics_counts_verified_claims_as_approved`.

## Cache recent Google discovery misses, but do not block the next quota window (2026-06-27)

Google ratings are stored on `businesses.google_*` once a listing has an accepted
`google_place_id`, so successful page display is already cached. The expensive
gap was the unrated discovery path: a business with no accepted `google_place_id`
could be text-searched again on every manual/admin sync, including all fallback
city/name searches, even if Google had just been queried minutes earlier.

Fix: `_run_sync_background` writes `google_lookup_attempted_at` when discovery
finishes with no accepted match or a duplicate-place conflict, and skips another
discovery lookup for six hours. Six hours is deliberate: it stops same-evening
manual reruns from burning paid Google quota, but normally expires before the
3:12 AM daily sync after an afternoon/evening cleanup, so fresh overnight quota
can still repopulate ratings. Do not lengthen this window casually; a longer
window can delay legitimate post-quota recovery. `RateLimitError` is not cached
as a miss because quota exhaustion is transient.

Successful matches clear `google_lookup_attempted_at` when storing
`google_place_id`/rating, so the marker is only a recent negative-discovery
cache. Regression coverage lives in `tests/test_google_places.py`:
recent misses skip Google entirely, no-match discovery records the marker, and
stale markers are retried and cleared on success.

## `www.<city>.<network>` 404'd — strip a leading `www.` in tenant resolution (2026-06-27, PR #422)

`www.miami.knowsbeauty.com` returned a 404 while `miami.knowsbeauty.com` worked.
Root cause is in `tenant.py::_match_suffix`: it strips the known network-domain
suffix, leaving everything to the left as the candidate city label. For a `www`
host that leftover is `www.miami` — two labels with a dot in it — and the matcher
deliberately rejects any multi-label remainder (`if "." in sub: continue`) because
nested subdomains aren't supported. So the `www` form found no tenant and 404'd.

Fix: strip a single leading `www.` in `resolve_tenant` **before** suffix matching,
so `www.<city>.<network>` resolves exactly like `<city>.<network>`. This is the
same shape as the existing `stage-`/`preview-` prefix stripping, just applied one
level earlier (to the whole host, not the city label) because `www` precedes the
city. Covers every city, not just Miami. Regression test:
`test_www_prefix_resolves_same_as_bare_city` in `test_smoke.py`.

Gotcha worth remembering: a `www` host that *does* have a TLS cert (Traefik served
a real cert with a `www.<city>` SAN) reaches the app and 404s at the application
layer — which looks like a routing problem but is actually this tenant-resolution
rule. By contrast `www.knowsbeauty.com` (the brand root, no city) fails earlier,
at TLS, with a self-signed cert because no Traefik router/cert exists for it — a
genuinely separate infra gap, not this code path. When a `www` host misbehaves,
check whether you're getting an HTTP 404 (app/tenant layer, this fix) or a
connection/cert failure (Traefik routing, infra).

## sitemap.xml and robots.txt must use the REQUEST host, not CANONICAL_BASE_URL (2026-06-20, PR #392)

This is a multi-tenant site: each city is its own website on its own subdomain
(`miami.knowsbeauty.com`, `hialeah.knowsbeauty.com`, `doral.knowsbeauty.com`, …),
and every page self-canonicalizes to its own host (the page-canonical logic in
`_base_context`, ~lines 340–383 of `routes/public/pages.py`, is correct: it keeps
the request's own subdomain for production hosts and only consolidates dev hosts
to the `.com`).

The bug: the `robots.txt` and `sitemap.xml` handlers built their base as
`canonical_base if canonical_base else f"{scheme}://{host}"`. Because
`CANONICAL_BASE_URL` is ALWAYS set to `https://miami.knowsbeauty.com` in
production, EVERY city's sitemap listed miami URLs and every city's robots.txt
`Sitemap:` line pointed at miami. Google discards sitemap entries on a different
host than the sitemap itself, so 25 of 26 city sites effectively had no sitemap of
their own pages — directly contradicting the (correct) self-canonical page tags.

Fix: `_seo_base_url(request)` (next to the other SEO helpers, just above
`_seo_show_live`) returns the right origin for the requesting host, mirroring the
page-canonical rule EXACTLY so the two never drift:
- no `CANONICAL_BASE_URL` → `{scheme}://{request_host}` (self-host);
- production host (request host == the canonical apex `knowsbeauty.com`, or ends
  with `.knowsbeauty.com`) → keep the request's own host, https from the canonical
  base (production always arrives over https);
- dev/staging host (`*.ai.devintensive.com`, `*.knowsbeauty.localhost`) →
  consolidate to the production `.com` base.

Both handlers now call it. **Do NOT** change the sitemap's apex/network `else:`
branch — it correctly builds each city's home URL from the request host's network
suffix (`tenant.network_domain_suffix`), because the apex landing page links out to
many different city subdomains. The apex branch uses `scheme`/`host` directly, not
`base`.

Live-verified via the admin-key `?preview_state=live` override (site still gated):
`hialeah.knowsbeauty.com/sitemap.xml` → 72 hialeah URLs (was 72 miami URLs);
`doral` → 74 doral; `south-beach` → 78 south-beach; `miami` → 318 miami (unchanged).
Each city's `robots.txt` `Sitemap:` now points at its own host. The page canonical
on a city home (`<link rel="canonical" href="https://hialeah.knowsbeauty.com/">`)
is unchanged — the fix touched only the two SEO files, not the per-page canonical.

Tests: `tests/test_seo_robots_sitemap.py` → `TestSeoBaseUrl` (helper cases + a
red-green guard proven by reverting to the old one-liner) and
`TestSitemapRobotsUseRequestHost` (end-to-end: a city's rendered sitemap/robots use
its own host while `CANONICAL_BASE_URL` points at a sibling city).

**General rule for this codebase:** any URL a city's own page emits about ITSELF
(canonical tags, sitemap `<loc>` entries, the robots `Sitemap:` line, og:url) must
use the request host on production subdomains — never `CANONICAL_BASE_URL`, which is
a single city's address. `CANONICAL_BASE_URL` is only for consolidating dev/staging
hosts onto the production `.com`.

## MKB-referred view tracking (2026-06-20, PR #389, KAT-039)

We now track which page views Miami Knows Beauty itself drove, not just that
views happened. The strategic point: a salon's free Google Business Profile
already shows "how people found you", so our "who found you" numbers are
churn-inducing redundancy UNLESS they prove a distinction Google can't — that
the visitor came from one of OUR pages (a guide, on-site search, a category /
neighborhood page, or a sister listing). Like the tap counters, this can't be
backfilled: capture the referrer at landing time or lose it forever.

**How "from within MKB" is decided:** `_is_mkb_referred(referer, host)` in
`pages.py` — a view is MKB-driven when the `Referer` header's host equals the
request's own host. On this network every internal page for a city edition is
served from that one host, so same-host == internal click. No referer (typed
URL / bookmark) or an external host (Google, social, the salon's own site)
counts toward the total only. The new `mkb_referred_view_count` is bumped in
the SAME `$inc` as `page_view_count`, in the same bot-filtered background task —
the flag is computed in-request (headers aren't available in the deferred task)
and passed into `_increment_business_view(business_id, mkb_referred)`.

**Badge attribution (closed 2026-06-20, KAT-040):** the "As Featured on Miami
Knows Beauty" website badge lives on the salon's OWN external site, so its
clicks refer from the salon's domain — an external host that same-host matching
can't credit. The original KAT-039 ship deliberately under-counted these. That
gap is now closed: the badge link carries a stable `?ref=mkb-badge` marker
(`MKB_BADGE_REF_MARKER` in `pages.py`, used by both the embed-code builder and
the dashboard preview link), and `_is_mkb_referred` takes a third `ref_marker`
argument that returns MKB-driven when the marker matches — even with an external
or absent referer. The marker is the ONLY external-referer carve-out; every
other external referer is still uncounted, so it's a tight carve-out, not a
loophole. The marker is NOT stamped on `listing_absolute_url` (which also feeds
the Instagram share caption and the preview link) — only on the dedicated
`badge_link_url`, so only a real badge click is credited as a badge click.
Bot filtering is unchanged (the marker check sits inside the same bot-gated
block). Like the rest of this counter, badge attribution can't be backfilled —
a marker-less badge link, once shoppers start clicking it, is indistinguishable
from any other external traffic forever, so the marker had to ship before
launch.

**It rides the existing snapshot machinery:** adding `mkb_referred_view_count`
to the `lifetime_actions` dict in `compute_report` means the monthly-report
snapshot/diff treats it exactly like the tap counters — one place, no new
plumbing. The dormant monthly email gains a "Miami Knows Beauty sent you N of
those visitors" line, shown only when N>0. Email stays dormant: no flag touched.

**Live-verifying a counter behind the preview gate:** the public business page
`/b/{slug}` is behind the preview gate, but the gate lets a valid `X-API-Key`
header through (admin-templates rule). So a real production view can be fired
with `curl -H "X-API-Key: $MKB_ADMIN_API_KEY" -H "Referer: ..." https://miami.knowsbeauty.com/b/{slug}`,
then the counter read back read-only from `who_knows_local` on do-server
(pymongo venv in `$HOME`, NOT `/tmp` — a stray `/tmp/inspect.py` shadows
stdlib; pass `MONGODB_ATLAS_URL` via stdin). Verified internal referer moves
both counters and an external (google.com) referer moves only the total.

## Editorial-guide quality audit (2026-06-20) — city_id type corruption + cross-network filing

A full quality read of all **156 live editorial guides** (not ~106) surfaced
three distinct data problems. Two were clear breakage and were fixed; the rest
are content-strategy calls left for review.

### Fixed: 14 satellite-city guides were invisible (city_id stored as ObjectId, not string UUID)

The Doral / Pompano Beach / Hialeah / Plantation / Pembroke Pines / Weston /
Miramar guides (2 each) had a Mongo **ObjectId** in their `city_id` field
instead of the string city UUID the rest of the system uses. The public guide
page resolves the tenant to a string city UUID and queries
`editorial_guides` by it, so these 14 guides matched nothing and returned 404 —
completely unreachable despite having real content and 6 live salons each.
Repointed each `city_id` (and `network_id`) to the correct existing beauty city
record; verified all 6 featured salons resolve live in each target city.
Rollback map: `do-server:/root/mkbwork/repoint_applied.json`.

**Symptom to watch for:** a guide that exists in the DB but 404s on its
subdomain. Check `type(guide["city_id"])` — if it's `ObjectId`, it can never
match a string-UUID city. Guard guide-insert paths to coerce/validate `city_id`
as a string that exists in `cities`.

### Fixed: archived a test-pollution guide

`test-api-ping-aventura` (title "Test", body "Test content.") was `status:
live`. Archived (reversible) — trivial leftover from API testing, not content.

### Flagged (NOT fixed — content-strategy call): cross-network + thin guides

- **~33 guides reference salons that live in a different network's city.** Spa,
  wellness, and health guides are filed under `beauty/miami` but their featured
  businesses were seeded into `wellness/miami` (and don't exist in beauty/miami).
  The page resolves featured slugs *scoped to the guide's own city*, so all the
  salon cards silently drop and the "Featured in this guide" section renders
  empty (the template hides it entirely when zero resolve). The prose still
  shows, naming salons it can't link to. **43 guides total render with an empty
  featured section.**
- **7 off-brand health guides** (dentists, primary care, physical therapy,
  healthcare-by-neighborhood) live under the Beauty network — they belong to a
  Health vertical, and their businesses were never seeded into beauty/miami.
- **~11 guides have empty bodies** (0 chars) and a few have <800 chars.
- **2 orphan Miami spa/wellness guides** (`city_id` `9755fe6a-…`, an unknown
  non-city UUID) — one has a 0-length body.

### Positives (the prose is genuinely good)

- **No templated/near-duplicate bodies** — 0 pairs above 60% similarity on the
  first 1,200 chars. The writing is original guide-to-guide (specific salon
  names, neighborhood-aware, distinct voice), not boilerplate with the
  neighborhood swapped.
- **No duplicate SEO meta descriptions** — every populated one is unique (16
  guides have none).
- **Core beauty guides resolve cleanly** — e.g. `best-balayage-miami` lists 6
  hair salons, all live in beauty/miami.

### The database trap (important)

Production reads/writes the **`who_knows_local`** database on the shared
Expertly Atlas cluster (`expertly.xuf7uv`). `deploy.md` says `known_around_town`
but that DB is empty — `architecture.md` (`who_knows_local`) is correct. The
running container's `MONGODB_DATABASE` env is what matters; verify against the
live API before querying. Read-only access for audits: do-server (Atlas
allowlisted) with a fresh pymongo venv at `/tmp/mkbvenv` and a clean cwd
(`/root/mkbwork`) — `/tmp` has a stray `inspect.py`/`pymongo` that shadows
imports if you run scripts from there.

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

## Search must be AND-across-words, not literal-phrase, and must search category + neighborhood (2026-06-19)

The pre-launch #1 shopper bug: searching "nails brickell" returned **0 results**.
`search_businesses` (`backend/app/services/content.py`) regex-matched the WHOLE typed
query as one contiguous string against only `name`, `short_description`, and `tags`.
No salon's name literally contains "nails brickell", so the search came up empty — and
it never searched `category_slugs` or `neighborhood_slugs` at all.

Fix (PR #355): split the query on whitespace; for each word build an `$or` across
`name`, `short_description`, `tags`, `category_slugs`, `neighborhood_slugs`; combine the
per-word blocks with `$and` (every word must match somewhere). So "nails brickell" now
returns salons that are BOTH nails AND in Brickell.

Key data-model fact: business documents store **only slug arrays** (`category_slugs:
["nails"]`, `neighborhood_slugs: ["brickell"]`), NOT human-readable category/neighborhood
names. For Miami the slug equals the typed word ("nails", "brickell", "hair", "wynwood"),
so matching the slug arrays covers real intent. A regex (substring, unanchored) match
also catches multi-word slugs from other city seeds (e.g. a "brickell" term matching
`brickell-ave-mary-brickell-village`). `mongomock-motor` matches `$regex` against array
elements exactly like real MongoDB, so the service tests are faithful. Tests:
`backend/tests/test_search.py` (red-green verified).

## Broken/missing salon photos: degrade to a branded placeholder, never a grey box (2026-06-19)

Some stock salon photos now 404, so cards showed a broken grey box; photoless cards
showed an empty grey box — looks like a broken directory. Fix (PR #356):
`backend/app/static/placeholder-salon.svg` (soft MKB gradient + brand mark), shown when
a photo is missing or fails to load.

- **Cards** (`partials/business_card.html`) use `<img>`: render the placeholder directly
  when no photo; add `onerror="this.onerror=null;this.src='/assets/placeholder-salon.svg';..."`
  (the `this.onerror=null` FIRST is the infinite-loop guard) when a photo is present.
- **Detail page** (`business.html`) uses CSS `background-image` (no `onerror` possible),
  so layer the placeholder as a SECOND background layer beneath the photo:
  `background-image: url("photo"), url("placeholder"); background-size: cover, contain` —
  if the photo 404s, the placeholder shows through.
- **Gotcha:** the precompiled `reference.css` ships **no `object-fit` utilities** —
  `object-cover`/`object-contain` classes have NO effect (they were already dead on the
  pre-existing card `<img>`). Set `object-fit` via inline `style=` instead. This is the
  same family as the admin-templates Tailwind-JIT rule: runtime/uncompiled classes are
  absent from the shipped CSS, so use inline styles or known-present classes.

- **Network landing page** (`network_landing.html`, the platform-root page listing live
  cities — rendered at the bare network host like `knowsbeauty.ai.devintensive.com`, no
  city subdomain) does NOT use the placeholder SVG, but it also must not fall back to a
  blank gradient. Its no-photo case now shows a branded city monogram + city name on top
  of the brand gradient. A city with a hero URL must carry that same branded fallback
  underneath the `<img>`, because a remote image can fail after render even when the URL
  exists. The fix (PR #432): keep `onerror="this.onerror=null;this.style.display='none';"`
  so a failed photo hides itself, but place the branded city fallback under the image so
  the error path reveals intentional content, not an empty capsule. (`this.onerror=null`
  FIRST is the loop guard, same as the card pattern.) Pick the fallback that matches the
  surface's existing no-photo design: cards/detail/home/guide/neighborhood →
  placeholder SVG; this page → branded city monogram/name over the brand gradient.

Tests: `backend/tests/test_image_fallback.py` (now also covers the network-landing
branded fallback) and `backend/tests/test_network_landing_hero.py` (covers missing
hero URLs and broken hero URLs). The `test_template_js_syntax.py` esprima guard only
scans `<script>` block bodies, so an `onerror=` HTML attribute is not checked by it.

## reference.css is a STATIC precompiled file — many Tailwind utilities are absent (2026-06-19)

`backend/app/static/css/reference.css` is the *only* stylesheet the site loads
(see `base.html`). There is **no Tailwind build step** — no `package.json`,
no `tailwind.config`, no PostCSS. The file is a fixed, hand-placed bundle copied
from the reference design. So a Tailwind class only takes effect if its selector
is literally present in that file; any class that isn't there silently does
nothing (no error, no visible style).

**Known-absent classes that the existing templates use as silent no-ops:**
`shadow-md`, `bg-amber-600`, `hover:bg-amber-700`, `shadow-black/30`,
`shadow-amber-*`, colored ring tints beyond `ring-amber-200` (e.g. `ring-amber-300`),
`ring-white/40`/`ring-white/50` (but `ring-white/30` IS present), `object-fit`
utilities, `border-t-4`, `inset-x-0`, `rounded-t-2xl`, `via-amber-500`, `to-white`.

**Before adding ANY class, verify it exists.** Selectors are backslash-escaped in
the compiled CSS — `px-2.5` is stored as `.px-2\.5`, `text-[10px]` as
`.text-\[10px\]`, `hover:shadow-xl` as `.hover\:shadow-xl`. A naive
`grep -F ".px-2.5"` gives a FALSE "missing". Correct check:

```bash
CSS=backend/app/static/css/reference.css
chk(){ esc=$(printf '%s' "$1" | sed -e 's/\./\\./g' -e 's/\[/\\[/g' -e 's/\]/\\]/g' -e 's/:/\\:/g' -e 's#/#\\/#g'); grep -qF ".$esc" "$CSS" && echo "FOUND $1" || echo "MISSING $1"; }
chk 'hover:shadow-xl'; chk 'text-[10px]'; chk 'shadow-md'
```

If a needed utility is absent, use an inline `style="..."` (as the card already
does for `object-fit`) or substitute a present class. Confirmed-present building
blocks for gold/amber accents: `bg-gradient-to-r`, `from-amber-400`,
`to-amber-600`, `ring-1`, `ring-amber-200`, `ring-white/30`, `shadow-lg`,
`shadow-xl`, `border-amber-200`/`-300`/`-400`.

## Verifying the gated production site (preview gate) — use the admin API key header (2026-06-19)

The site is behind the preview gate (`PreviewGateMiddleware`). The
`/tmp/mkb-walkthrough/walkthrough_auth.py` recipe sets a `preview_token` cookie,
but those session tokens expire (30-day `preview_sessions` rows) and the saved
`preview_token.txt` is often stale → every request 302s to `/preview-login`.

The reliable bypass: send the **admin API key** as an `X-API-Key` header on every
request. `PreviewGateMiddleware.dispatch` checks `X-API-Key == admin_api_key`
*before* the cookie and lets it through. The key is `MKB_ADMIN_API_KEY` in
`~/.claude/gitignore/creds`. In Playwright:

```python
ctx = browser.new_context(extra_http_headers={"X-API-Key": MKB_ADMIN_API_KEY})
```

This renders every public page (home, `/c/*`, `/n/*`, `/b/*`) for screenshots
without minting a fresh preview session. Featured salons (paid tier) currently
include `the-spa-at-the-setai`, `the-spa-at-st-regis-bal-harbour`,
`skinspirit-aventura`, `rossano-ferretti-hair-spa-miami`. The seed (`seed_miami`)
programmatically sets `featured: {enabled: True, tier: "premium"}` on ~36
businesses — this flag is NOT in `_real_businesses.json`, so don't conclude
"nothing is Featured" from that file alone.

## Never promise "forever" or "locked-in" in owner copy (2026-06-19)

Standing owner instruction: the site must **never promise permanence or a price
lock**. The Founding Partner copy used to tell salons their badge and pricing
were "permanent", "forever", and "locked-in" — promises the product doesn't
actually back. PR #360 removed every such phrase while keeping the Founding
Partner concept (gold badge, limited spots) and replacing the over-promises with
honest wording ("recognized as a Founding Partner with a gold badge on their
listing"; "visible to visitors" instead of "visible to every visitor, forever").

Where the over-promises lived (all fixed): `services/copy.py` claim body,
`templates/business.html` claim-banner fallback, `templates/pricing.html`
callout, `templates/owner_me.html` (welcome banner, the "Lock in Founding
Partner pricing before rates increase" bullet — removed entirely, and the badge
banner), `services/owner_email.py` claim-verified urgency ("left at the founding
price" → "left."), and `static/walkthrough/mkb-owner-outreach-preview.html`.

Two distinctions that matter when touching this:
- **Keep, don't remove, the accurate "free forever" lines** — `pricing.html`
  "Your listing stays live forever as a Free listing" and `owners.html` "Free
  forever to stay listed." are TRUE (free listings stay free), so they stay.
- **"Permanent" as a code-behavior note ≠ a user promise.** The
  `is_founding_partner` flag genuinely is not cleared by the cancellation webhook
  today, so the badge section lives outside the subscription conditional. That's
  an internal persistence fact (fine to state in a WHY comment), but the
  user-facing copy must not advertise it as a permanence guarantee.
- **Seed descriptions legitimately contain "permanent"** (e.g. "permanent
  makeup", "Permanent Eyeliner" — real beauty services). So a regression guard
  must assert the specific over-promise phrase ("permanent Founding Partner
  status", "permanent gold badge", "locked-in pricing") is absent — never the
  bare word "permanent" on a page that renders salon descriptions.

Regression guards: `tests/test_founding_partner_copy.py` (copy default) and a
`TestFoundingPartnerNoPriceLockPromise` class in `tests/test_owner_email.py`
(red-green verified). Three smoke tests had codified the old wording and were
updated to the corrected copy plus negative guards.

## Founding Partner removed entirely — only dead data + cleanup migration remain (2026-06-19, PR #362)

The owner decided to drop the Founding Partner concept altogether (the badge,
the "spots left" scarcity, the granting). PR #362 stripped ALL of it: the public
badge (deleted `partials/founding_partner_badge.html` + every include on cards
and the detail page), the owner-dashboard celebration banner and badge section,
the pricing/walkthrough/owners/claim-form copy, the claim-verified email
urgency, the outreach templates, the checkout + claim-verify grant logic, the
`founding_partner_cap` config, and the per-page founding-count context.

Three things were deliberately KEPT (so don't "finish the job" by removing them):
- **The paid Featured tier** (`business.featured.enabled` / `featured.tier`) and
  its champagne-gold `✦ Featured` badge, plus Editor's Pick — a separate paid
  product, untouched.
- **The "Get Featured — $29/month" upgrade CTA** on `owner_me.html` — the
  revenue path. The card was only re-labelled (was "Founding Partner offer", now
  "Get Featured"); button, bullets, and checkout flow are unchanged.
- **The `is_founding_partner` model field and the
  `clear-seeded-founding-partner-flags-20260611` startup migration in
  `database.py`** — left exactly in place as harmless dead data/cleanup. The
  invariant going forward: `grep -rniE 'founding' backend/app` should return
  ONLY those two locations. Anything else is a regression of this removal.

Note: the seed scripts (`backend/seed/*`) still write `is_founding_partner:
False` and `seed_miami.py` still reads it from the seed JSON — but no seed JSON
ever sets it true, so the seed never grants the badge (it's inert dead data).
Left untouched to avoid editing the production-reset seed path for no behavior
change. If FP ever needs to be excised from seeds too, do it as its own change.

Tests: deleted `test_founding_partner_copy.py`; converted the grant/badge tests
in `test_stripe_billing.py`, `test_admin_claims.py`, and the owner-dashboard
smoke tests into negative guards (flag set in DB → still NO badge rendered);
the `test_startup_migrations.py` tests that protect the kept migration still
pass unchanged.

## The AI caption "voice per category" table must track the LIVE category slugs (2026-06-20)

The Featured-tier AI tool writes captions + ad copy "in the salon's voice."
Part of that voice is a per-category style note in
`backend/app/services/ai_caption.py` (`CATEGORY_STYLE_NOTES`), keyed on
`Business.category_slugs`. Unknown slugs fall back to `DEFAULT_STYLE_NOTE`
(generic "warm and professional").

The table had drifted from reality: it was keyed on an older naming scheme
(`skin`, `lashes-brows`) and had NO entry for high-volume live categories
like `spa`, `lash-brow`, and `waxing`. Result: ~32% of live businesses
(330 of ~1,000 — including 271 across just spa/lash-brow/waxing) silently
got the generic voice instead of a tailored one. The captions were still
good — the salon's real neighborhood, services, and `known_for` carry most
of the quality — but those salons lost the on-brand voice the feature sells.

Fix (PR #371): extended the table to cover every live primary-category slug
(`spa`, `lash-brow`, `waxing`, `skincare`, `aesthetics`, `holistic`,
`iv-hydration`, `recovery`, `sleep-stress`, `longevity`, `fertility`,
`nutrition`, `retreats`, `yoga-meditation`, `pt-recovery`), keeping the old
names as synonyms. The caption/ad-copy prompt wording and output format were
NOT changed. Added `test_style_note_covers_real_production_slugs` to pin the
live slugs so a future rename can't quietly regress coverage again.

How to re-check coverage against live data (read-only, from an Atlas-
allowlisted host like `do-server`): aggregate distinct primary
`category_slugs` on `{status:"live"}` in the `who_knows_local` database and
compare against `CATEGORY_STYLE_NOTES.keys()`. If a NEW vertical appears in
the catalog, add its slug both to the table and to the test's
`production_primary_slugs` list.

Quality note: exercising the real generator against the live gateway on real
salons (hair, nails, med-spa, barber, brow bar, spa) showed the output is
genuinely good — specific to each salon, cliché-light, smart local+niche+
branded hashtags. No prompt rewrite was warranted; the only real gap was
this category-coverage one.

## "As Featured on Miami Knows Beauty" website badge — embeds must clear the preview gate (2026-06-20, PR #379)

KAT-037 added an embeddable website badge: a Featured salon drops a copy-paste
`<a><img></a>` snippet on its own site footer; the link points to the salon's
listing (`{origin}/b/{slug}`) so the salon's visitors reach its directory page,
and every embed is a backlink to us. The badge image is served at
`GET /badge/featured.svg` (a dynamic route in `routes/public/badge.py`, NOT a
static `/assets/` file).

Key gotchas / decisions:

- **The badge image MUST be reachable past the preview gate**, because it is
  embedded on EXTERNAL salon sites. Without an exemption every embedded badge
  302s to `/preview-login` (which a salon's visitor can't follow) and renders as
  a broken image. The fix: add ONLY the `/badge/` prefix to
  `_BYPASS_PREFIXES` in `middleware/preview_gate.py`. It serves nothing but the
  static brand-mark SVG, so the exemption leaks no gated directory content.
  Red-green verified in `test_badge.py` (remove the entry → the bypass test
  fails; normal pages `/`, `/c/hair` still 302).

- **Dedicated `/badge/` route, not `/assets/`**: `/assets/` already carries the
  login page's own CSS/JS, so a prefix exemption there is broader than wanted.
  A dedicated `/badge/` prefix keeps the gate exemption tight and unambiguous.
  Register the badge router BEFORE the public SSR catch-all in `main.py` (same
  ordering reason as `media.py`).

- **Absolute listing URL for the embed**: a relative `/b/slug` would resolve
  against the SALON's domain, not ours. Build the embed link from
  `CANONICAL_BASE_URL`'s origin (the production `.com`) when set, falling back to
  the request origin. Computed in the `/owners/me` handler in `pages.py`
  (`listing_absolute_url`, `badge_image_url`, `badge_embed_code`,
  `share_caption`), all gated to Featured owners (`is_subscribed`).

- **Badge SVG sizing**: the serif "Miami Knows Beauty" wordmark needs a
  340-wide viewBox at font-size 20 to clear the rounded right corner. The first
  cut at 300-wide clipped the final letter — always render the badge (headless
  Playwright → PNG → Read) and eyeball it; the viewBox math is easy to get
  wrong. Slugs are `[a-z0-9-]`-only (`_validate_real._slugify`), so the embed
  code and `<a href>` have no injection surface; Jinja autoescaping in the
  `<pre>` is belt-and-suspenders.

- **Copy buttons**: reused the dashboard's existing clipboard pattern
  (navigator.clipboard with an execCommand fallback for http dev) via a small
  reusable `wireCopier(btnId, sourceId, flashId, errId)` IIFE. `textContent` of
  the `<pre>`/`<p>` yields the DECODED embed HTML / caption — exactly what the
  owner pastes.

- **The badge does NOT depend on `MARKETING_AI_ENABLED`** — it's a static asset
  plus a templated caption, so it works regardless of the AI feature flag.

## Sitemap 500 on string-dated guides — would have broken launch day (2026-06-20)

The launch plan is a single flip of the preview/launch gate: while it's ON,
`robots.txt` returns `Disallow: /` and `sitemap.xml` is an empty `<urlset>`
(both short-circuit on `get_preview_mode_enabled()`); when it's OFF, both render
their live form. That part already worked. The trap: the live `sitemap.xml`
formats each editorial guide's `<lastmod>` from `updated_at`/`published_at` by
calling `.strftime()` — but ~25 of Miami's 107 live guides store that field as
an ISO STRING (same import quirk that 500'd the guide PAGE in PR #377, fixed
there with the `iso_datetime` filter). `.strftime()` on a `str` raises
`AttributeError`, which 500s the WHOLE sitemap. Because the gate is on today the
sitemap is empty, so the crash was invisible — it would have fired the instant
David flipped the gate, turning launch into an invisible-to-Google outage.

Fix: a shared `_lastmod_str(raw, fallback)` helper in `pages.py` that accepts a
datetime, an ISO string (first 10 chars are `YYYY-MM-DD`), or anything else
(fallback) — used for BOTH the business loop and the guide loop. Lesson: any new
code that calls `.strftime()` on a stored timestamp in this DB must assume the
value might be a string; prefer `_lastmod_str` / the `iso_datetime` filter.

Two more SEO touches landed in the same change:
- `_seo_show_live(request)` is now the single decision both `robots.txt` and
  `sitemap.xml` read, so they flip together on one gate change. It also honours
  an admin-key-gated `?preview_state=live|gated` override so the live response
  can be verified on the deployed site BEFORE launch without flipping the real
  gate (anonymous requests with the param still get the gated form — no early
  slug leak).
- The bare-apex sitemap (no city subdomain) now lists each city's home page on
  its own subdomain, so a brand-new city is discoverable via the sitemap, not
  only by crawling the landing-page HTML. City URLs are built from the request
  host's network suffix (not `CANONICAL_BASE_URL`, which is a single city's
  domain).

## Monthly "your listing is working" retention email — dormant build (PR #384, 2026-06-20)

The #1 churn risk from the strategy review: a Featured owner pays $29/mo, the
dashboard shows real stats, but nothing PUSHES them. Built a monthly email that
does — and kept it OFF by default.

- **"Views this month" from a lifetime-only counter:** the business doc only
  carries `page_view_count` (lifetime). To get a per-month number we snapshot
  that counter once per month into `monthly_view_snapshots` ((business_id,
  period_key) unique) and diff: views_this_month = lifetime_now − the most recent
  snapshot from a period BEFORE this one. The honest caveat (documented in the
  module): if a report runs mid-month, "this month" really means "since the last
  report," not a strict calendar slice. The first-ever report has no prior
  snapshot, so it reports lifetime as "since you joined" rather than inventing a
  monthly figure. Messages need NO snapshot — `business_inquiries` rows carry
  `submitted_at`, so it's a direct half-open date-range count.
- **Idempotent same-month reruns:** the current period's snapshot is the baseline
  for NEXT month, so a second report in the same month must NOT overwrite it (or
  the delta collapses to ~0). `_latest_snapshot_before` uses `period_key < current`
  strictly, so it always skips the current month's own row. Tested explicitly.
- **Small numbers can accelerate churn** (per the strategy review): so under 10
  views/month the email drops the big stat strip and leans on a ready-to-post
  caption (reusing `ai_caption.generate_caption`) instead of dwelling on the
  number. Trend-up months lead with "up from N last month."
- **Dormant-feature pattern, three send-safety layers:** (1) admin-key gate on the
  route, (2) `MONTHLY_REPORT_TEST_SEND_ENABLED` off by default gates the actual
  Resend call, (3) the test-send route refuses any `to` that matches a real
  `claimed_email` (409). There is NO cron / bulk sender — the live monthly send is
  the founder's call, marked by the reserved `MONTHLY_REPORT_LIVE_SEND_ENABLED`
  flag that nothing reads yet. The preview route renders HTML and sends nothing.
- **Founder-owned copy** (subject + headlines) lives in clearly-labelled constants
  at the top of `monthly_email.py` so David can tweak the pitch without hunting.

## Shopper-action click tracking via server-side redirect routes (PR #387, 2026-06-20)

KAT-038 added per-listing counters for the three highest-intent shopper taps —
tap-to-call, tap-for-directions, website click — alongside the existing
`page_view_count`. They're lifetime counters on the business doc, `$inc`-ed in a
background task with the same `_BOT_UA_FRAGMENTS` filter page views use.

- **Tracking is server-side, not JavaScript.** The listing's phone/directions/
  website links point at lightweight redirect routes `GET /b/{slug}/go/{call|
  directions|website}` (in `routes/public/pages.py`). Each route resolves the
  business by tenant+slug, bot-filters, `$inc`s the matching counter in a
  background task (no added latency on the tap), then **302**s to the real
  `tel:` / Google Maps / website target. Works with JS off and can't be missed.
  Returns **404** when the salon has no target for that action (no phone/website/
  address) — never count a tap that reaches nowhere. An `_ACTION_COUNTER_FIELDS`
  dict maps the URL action segment to the DB field so an unknown action can't
  `$inc` an arbitrary field (it 404s before any DB hit).
- **Use 302, NOT 301.** A 301 is cached by the browser, so the next tap would
  skip the server and never be counted. 302 keeps every tap flowing through.
- **`directions_url` in `business.html` is now only a render guard.** The link
  `href` is `/b/{slug}/go/directions`; the raw Maps URL is still computed
  (`_directions_url_for_business`, shared by the page and the redirect route) and
  passed to the template so the link only renders when a real destination exists,
  and for structured-data/no-JS fallback. JSON-LD keeps the RAW phone/url.
- **Website redirects force `https://`.** A stored website without a scheme
  (`example.com`) would make the 302 Location browser-relative and dead-end
  against our own domain; a non-http scheme (`javascript:`) must never become the
  target. `_action_target_url` passes http(s) through, else prepends `https://`
  and strips any other scheme prefix.

### Testing a `tel:` redirect: httpx (TestClient) can't parse the Location

`fastapi.testclient.TestClient` wraps **httpx**, which eagerly URL-parses every
`Location` header to build the Response — and **rejects a `tel:` value as an
invalid URL, raising `httpx.InvalidURL` before you can read it**, even with
`follow_redirects=False`. `http(s)` redirects (website, directions) test fine
with `TestClient(app, follow_redirects=False)` and `r.headers["location"]`.

For the `tel:` route, don't fight httpx and don't drive the raw ASGI app by hand
(the background task runs in Starlette's anyio task group, which conflicts with a
manually-spun `asyncio.run` loop and the mongomock client's loop — you get a
TaskGroup exception). Instead:
1. Assert the **exact `tel:` target string** directly on the resolver
   (`_action_target_url("call", {"phone": "(305) 555-0142"}) == "tel:3055550142"`)
   — pure function, no HTTP.
2. Assert the **route increments the counter** by calling `client.get(...)` inside
   a `try/except httpx.InvalidURL` (the request fully reached the server and ran
   the background `$inc` BEFORE httpx choked on the response), then read the count.
`TestClient` runs background tasks synchronously, so the `$inc` is visible
immediately after the request. See `tests/test_shopper_actions.py`.

### Monthly email taps mention reuses the snapshot-diff mechanism

`monthly_report.py` already snapshots the lifetime view counter per month and
diffs to get "views this month". The three tap counters are stored in the SAME
snapshot row and diffed identically (`_action_delta`), so the dormant monthly
email can mention non-zero taps ("Of those, N tapped to call ...") with the same
honest "since you joined" fallback on the first report. The email stays fully
dormant — no `MONTHLY_REPORT_*_ENABLED` flag was touched.

## Right-size photos at render time — the `img_sized` Jinja filter (PR #394, 2026-06-20)

The mobile homepage weighed **~6.6MB** (15 images = 6.4MB on a 390px viewport).
Two causes: photo URLs came straight from stored data with desktop-poster widths
baked in (a `?w=2400&q=90` Unsplash photo shipped to a 390px phone is ~6× the
pixels the screen shows), and one neighborhood tile used an unoptimized 1.9MB
PNG. After this change the homepage is **~1.16MB of images / 1.33MB total** —
about an 82% cut — with no visible quality loss.

Key facts for the next person:

- **`img_sized(url, width)`** is registered on the shared Jinja env in
  `main.py` (next to `fmt_time`). It rewrites `w=` and caps `q=` at 70 **only**
  for `images.unsplash.com` URLs; every other URL (the placeholder SVG, a
  relative `/static` path, a non-Unsplash CDN like a Tilda PNG) is returned
  untouched. Uses `urllib` (parse/rebuild the query), never regex — a regex
  silently mishandles the "no `w=` present" and "`w` in a path segment" cases.
- **Apply it at the render site with the width that element shows at** — the
  sizing decision belongs next to the layout (hero 1200, full-bleed tiles 800,
  cards 500, small thumbnails 200, business-detail hero 1000). It's wired into
  home, category-via-`business_card.html`, neighborhood, business, network-
  landing, and editorial-guide templates.
- **Do NOT size the social-share image (`og:image` / `twitter:image`).** Those
  are emitted raw by `base.html` (no filter) and SHOULD stay large — preview-card
  platforms want a big image and the browser never downloads it to paint the
  page, so it doesn't count toward page weight. A page-wide "no `w=2400`
  anywhere" assertion is therefore WRONG; assert on the visible hero's
  `background-image`, not the whole page text (this bit the first draft of
  `test_img_sized.py`).
- **Do NOT size the lightbox `data-photos` on `business.html`** (line ~408) —
  that's the full-resolution zoom view; users open it to see detail.
- **The 1.9MB PNG can't be shrunk by a URL param** (it's a non-Unsplash CDN),
  so it was swapped for a sized Unsplash salon photo in BOTH the seed
  (`_photos_by_slug.json`) and the live DB. A full scan across all 29 cities
  found it in exactly ONE live record: the `sunny-isles-beach` neighborhood
  (`photo_url`), fixed via `PATCH /api/v1/neighborhoods/{id}` (admin key).
- **Pre-existing tests that string-matched a stored URL break** when you add the
  filter: `test_image_fallback.py` renders the card partial through a BARE
  `jinja2.Environment` that doesn't know `img_sized` (register the real filter on
  it), and `test_smoke.py`'s string-photo test asserted the exact `?w=800` URL
  (now assert the stable photo-id path segment, which proves the real photo
  rendered rather than a placeholder).

## Editorial guide tenancy — featured salons must be in the SAME city as the guide (2026-06-21)

When creating an editorial guide (`POST /api/v1/editorial-guides`), the guide's `city_id` must match
the `city_id` of every salon it features. Two reasons, both in `editorial_guide_page`
(`backend/app/routes/public/pages.py`, ~line 1549):

1. **Slug→business resolution is city-scoped:** the fallback lookup is
   `businesses.find({"city_id": <guide's city>, "slug": {"$in": business_slugs}})`. A guide whose
   `city_id` is A cannot resolve salons whose `city_id` is B — they silently fail to render as
   featured business cards and the `ItemList` structured data comes out empty (the body markdown still
   renders, so the page looks *almost* right — only the linked salon cards + ItemList are missing).
2. **Salon `/b/` links are host-based:** a salon's listing page only exists on its own city's
   subdomain. A guide on `miami` that links to a North-Miami-Beach salon's `/b/` page 404s, because
   that listing lives on `north-miami-beach.knowsbeauty.com`, not the flagship.

`featured_business_ids` resolves by `_id` (not city-scoped), but it would still emit broken
cross-tenant `/b/` links — so **same-city is the real constraint**, not just a resolution detail.

**Tenancy model:** the Miami flagship city holds the CORE neighborhoods' salons (Coconut Grove,
Brickell, Wynwood, etc. are miami-city records — which is why the flagship hosts ~107 guides covering
them). Outer areas (North Miami Beach, Doral, Hialeah, and the Broward cities) are their own city
subdomains with their own salons and guides. So: a guide for a core-Miami neighborhood goes on the
flagship; a guide for an outer city goes on that city's subdomain.

**Symptom that caught this:** a new "Best Nail Salons in North Miami Beach" guide rendered its salon
names (markdown headers) but no linked cards and an empty ItemList when placed on the flagship;
moving its `city_id` to `north-miami-beach` (where the salons live) made all 5 cards, links, and the
ItemList render correctly.

## Revenue-path security hardening — allowlist public fields without breaking shopper data (2026-06-30)

The public business API should use an explicit allowlist, but that allowlist is not
"only identifiers and names." Shopper-facing profile fields such as public phone,
website, booking URL, descriptions, SEO overrides, `voice_phone_number`, ratings,
and social/contact data are part of the public contract. The sensitive side is
owner/billing/vendor/internal data: `claimed_email`, Stripe ids, VAPI ids, import
payloads, scoring/counters, and dead revenue flags like `is_founding_partner`.

Two gotchas from KAT-075:

- When `ADMIN_API_KEY` fails closed, admin-page tests that previously relied on
  an unset-key dev bypass must send explicit `ADMIN_HEADERS`; otherwise unrelated
  admin tests fail with 401 even though their behavior is otherwise unchanged.
- Claim rows are not an ownership source of truth until admin verification writes
  the business document. Owner inquiry routing should trust only
  `business.claim_status == "verified"` plus `business.claimed_email`, never a
  forged or stale `business_claims` row or owner-session artifact.
