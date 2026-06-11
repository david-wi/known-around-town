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
