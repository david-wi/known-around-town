
## Post-payment confirmation banner (2026-06-13)

The confirmation banner (`id="subscribed-banner"`), URL-param stripping, click-to-dismiss, and JS toast are all already implemented in `owner_me.html`. The two gaps were: (1) the banner used generic green (`bg-emerald-700`) instead of the amber theme used everywhere else for "Featured" branding, and (2) there was no auto-dismiss timer — the banner stayed until manually clicked.

Fixed in PR #207: amber colour (`bg-amber-600`) applied to both banner and toast; 10-second auto-dismiss added via `autoDismissTimer = setTimeout(dismissBanner, 10000)` with `clearTimeout` called on manual dismiss.

The server only shows the banner when BOTH `?subscribed=1` is in the URL AND `stripe_subscription_id` is set on the business — so a bookmarked URL without a real subscription shows nothing. The JS then strips `?subscribed=1` from the URL immediately so a page refresh never re-shows it.

## Seed script preserves archived status (2026-06-13)

The upsert helper in `seed/_helpers.py` does a full document replace on re-seed, preserving only `_id` and `created_at`. Without a guard, manually-archived businesses come back to life on every midnight seed run.

The fix: `if existing.get("status") == "archived" and doc.get("status") == "live": doc["status"] = "archived"` — added right before the replace_one call in `upsert()`.

The seed runs via `scripts/deploy.sh` (sets `KAT_ALLOW_PRODUCTION_RESET=true`) on every nightly container restart. Watchtower picks up new images and restarts at midnight.

The database serves THREE networks simultaneously (beauty `eb913a29`, wellness `9bf1b71d`, health `a6486f6d`) under one `who_knows_local` DB. Always filter by `network_id` when counting beauty businesses — counts without that filter include all three networks and will look wildly inflated.

## Preview login email delivery (2026-06-12)

Resend IS configured and working (`RESEND_API_KEY=re_PHtBvPRq_...`). When a code email doesn't arrive, the problem is Gmail-side filtering, not the server. The bypass link pattern (`/api/v1/preview/set-session?token=X&next=/`) is the right unblock — generate one by running the Python snippet in the backend container (see the session that created PR #205 for the exact script).

As of PR #205, every issued code is also logged at INFO level to the container — `docker logs known-around-town-backend-1 | grep "Preview code"` shows the code immediately without a DB query.

The allowed email list is in `backend/app/services/preview_auth.py` (`ALLOWED_EMAILS` + `ALLOWED_DOMAINS`). David's personal emails (`david@bodnick.com`, `david@wisdev.com`) are already in it.

## Removing closed businesses from seed data (2026-06-13)

The upsert archived-status guard (PR #206) only protects businesses that ALREADY exist in the DB as archived. A business defined in `_real_businesses.json` with no `status` field gets freshly INSERTED as "live" on every seed run, bypassing the guard entirely.

Permanent fix: remove closed businesses from `_real_businesses.json` entirely. The nightly seed cannot re-insert what isn't in the source data.

After removing a business from the JSON, its DB record persists as "archived" (protected by the upsert guard). That's the correct final state: visible in DB for historical audit, but never re-surfaced live.

When updating smoke tests to remove a closed business as a test target, pick a replacement that: (a) exists in the seed, and (b) for homepage-trending tests, also appears in `trending_business_slugs` in `seed_miami.py`.

## Google ratings display (2026-06-14, PR #281)

`google_rating`, `google_review_count`, `google_place_id`, `google_rating_synced_at` were already on the Business model and the admin sync UI was already built — nothing to re-implement there. Only `hide_ratings: bool = False` was missing.

The ratings threshold (`ratings_min_review_count`) is a site setting injected as a Jinja2 global in `main.py` (same pattern as `support_email`). This makes it available on every template — home, category, neighborhood, search, business detail — without per-route DB queries. The global is set to 20 at module load, overwritten from the DB in `on_startup`, and refreshed in-process when the admin saves the settings page. No restart needed to change the threshold.

Template condition used in both `business.html` and `business_card.html`:
```jinja2
{% if b.google_rating and not b.hide_ratings and (b.google_review_count or 0) >= (ratings_min_review_count or 20) %}
```
Note `business_card.html` uses `b` (not `business`) as the loop variable.

**Admin business edit page added in PR #282.** Routes: `GET /admin/businesses` (search), `GET /admin/businesses/{id}/edit`, `POST /admin/businesses/{id}/edit`. Module: `backend/app/routes/admin/businesses_admin.py`, templates: `admin/businesses.html` and `admin/business_edit.html`. Follows the same `attach_templates()` + `require_admin` pattern as all other admin routers.

**Docker compose restart gotcha (2026-06-14):** When you run `docker compose up -d` from the repo root without specifying `-f docker-compose.prod.yml`, Docker uses the dev `docker-compose.yml` which builds the image locally (not from GHCR) and exposes port 8000 directly without Traefik labels. The result: the app responds internally on port 8000 but Traefik can't route to it, so external requests return 404. Always use `docker compose -f docker-compose.prod.yml up -d backend` on the production server. If a container ends up with no Traefik labels and a direct port binding, pull and restart with the prod compose file.

## Category slugs in the DB (2026-06-14)

The real category slugs used in `category_slugs` on business documents are short single-word slugs: `hair`, `nails`, `lash-brow`, `barber`, `spa`, `waxing`, `makeup`, `med-spa`. They do NOT use the longer descriptive form (`hair-salons`, `nail-salons`, `lashes-brows`, etc.). Always verify against the `categories` collection before writing category slugs — mismatched slugs write silently but the category filter and card labels break. The `assign_categories.py` script in `backend/scripts/` documents the correct mapping.

## Support email configuration (2026-06-12)

The support email `hello@knowsbeauty.com` was hardcoded in ~15 places across templates and email service code. The domain has no mail records so every message to it bounced. The pattern used to make it configurable:

1. `Settings.support_email` in `config.py` (env var `SUPPORT_EMAIL`)
2. Jinja2 global set at module load from env var, overwritten in `on_startup` from DB value
3. `get_support_email()` in `site_settings.py` — DB value takes precedence over env var
4. Admin settings page field saves to DB and updates the Jinja2 global in-process immediately

For any future site-wide text that might need to change: use this same DB-over-env-var-over-default pattern from `site_settings.py`.
