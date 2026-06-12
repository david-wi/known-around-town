# Epic: Foundation — platform infrastructure, Docker, CI, multi-tenant

### KAT-001 — Docker-containerized FastAPI backend · V1 · implemented
**Persona:** David (operator), Posey (AI PM).
Single `backend` Docker service running Python 3.12 + FastAPI, deployed on a
DigitalOcean droplet behind Traefik. Image built in GitHub Actions and pushed to GHCR.
**Acceptance:** Given a push to `main`, when GitHub Actions completes, then a new
`:latest` image is available at `ghcr.io/david-wi/known-around-town:latest` and the
container on the production server restarts within 5 minutes via Watchtower.

### KAT-002 — Watchtower auto-deploy · V1 · implemented
**Persona:** David (operator).
Watchtower polls GHCR every 5 minutes for a new `:latest` image and automatically
restarts the `backend` container when one is found — no manual SSH needed for code
changes.
**Acceptance:** Given a merged PR, when 5 minutes pass, then `docker compose ps`
shows the `backend` container running the new image SHA.

### KAT-003 — MongoDB Atlas integration · V1 · implemented
**Persona:** David (operator).
App connects to MongoDB Atlas (`who_knows_local` database) via Motor async driver
with `tz_aware=True`. All collections are created on first insert; indexes are
created at startup via `ensure_indexes()`.
**Acceptance:** Given a fresh container start with a valid `MONGODB_URL`, when the
health endpoint returns `{"status": "ok"}`, then all required collections and indexes
exist in Atlas.

### KAT-004 — Startup migrations · V1 · implemented
**Persona:** David (operator).
One-time idempotent migrations run at startup via `run_startup_migrations()`,
tracked in the `app_migrations` collection so each migration only runs once even
across restarts.
**Acceptance:** Given a migration that has already run, when the container restarts,
then the migration does not run again and `app_migrations` shows it completed.

### KAT-005 — Multi-tenant network routing · V1 · implemented
**Persona:** David (operator), future city/vertical operators.
The platform supports multiple networks (e.g., beauty, wellness) and cities.
`NETWORK_DOMAINS` env var maps `slug:domain` pairs. The app resolves incoming
`Host` headers to the correct network and serves city-specific content.
**Acceptance:** Given `NETWORK_DOMAINS=beauty:miami.knowsbeauty.com`, when a
request arrives at that hostname, then the app serves Miami/Beauty content; when
a request arrives at a hostname not in the map, then a 404 is returned.

### KAT-006 — CI test suite (GitHub Actions) · V1 · implemented
**Persona:** David (operator), Posey.
All tests run automatically on every push to `main` via GitHub Actions. The suite
covers backend routes, billing, preview gate, owner portal, and admin paths.
**Acceptance:** Given any push to `main`, when GitHub Actions completes, then all
372+ tests pass or the PR is blocked from merging.

### KAT-008 — Pydantic-to-MongoDB serialization excludes unset optional fields · V1 · implemented
**Persona:** David (operator).
`to_doc()` in `_crud.py` must call `model.model_dump(by_alias=True, exclude_none=True)`
so that optional fields that haven't been set are absent from the stored document rather
than written as explicit `null`. MongoDB sparse-unique indexes (e.g. `stripe_customer_id_1`)
include documents with the field set to `null` — only documents where the field is
entirely absent are excluded. Writing `null` therefore consumes the one "null slot" and
causes every subsequent `INSERT` to raise `DuplicateKeyError`.
**Acceptance:** Given a new `Business` with no Stripe identifiers, when `to_doc()` is
called, then `stripe_customer_id` and `stripe_subscription_id` are absent from the
returned dict (not present-and-null). Covered by `test_new_business_omits_unset_optional_fields`.

### KAT-007 — Environment-variable-driven configuration · V1 · implemented
**Persona:** David (operator).
All secrets, feature flags, and configurable parameters are read from environment
variables at startup. No secrets are committed to the repository.
**Acceptance:** Given a new env var (e.g., `PREVIEW_MODE_ENABLED=false`), when the
container is restarted, then the new value takes effect without a code deploy.
