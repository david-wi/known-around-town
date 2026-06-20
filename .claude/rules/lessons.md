
## Guide pages 500 when published_at is stored as a string, not a datetime (2026-06-20, PR #377)

A pre-launch sweep of every page TYPE across all 26 city editions (1,800+ live
pages) found that **23 editorial guide pages on Miami returned HTTP 500** while
every other page type (business, category, neighborhood, cross, home, static,
404) was solid. Root cause: `editorial_guide.html` emitted the schema.org
`datePublished` with `guide.published_at.isoformat()` — called directly, no type
guard. A batch of imported guides stored `published_at` as a plain ISO string
("2026-06-12T06:00:00Z") instead of a datetime, and a `str` has no `.isoformat()`,
so the whole page crashed (`AttributeError`). The page's *other* date spot
(the human-readable byline) already used the `humantime` filter, which guards
with `isinstance(when, datetime)` — so it survived; only the unguarded JSON-LD
line crashed.

Fix: added an `iso_datetime` Jinja filter (mirrors `humantime`: datetime ->
`.isoformat()`, string -> passthrough, empty -> "") and routed the template
through it. There are now ZERO unguarded date-method calls in any public
template (`grep -rE '\.(isoformat|strftime|year|month|day)\(' templates/*.html`).

Two related data observations (NOT fixed in this PR — they're data/strategy calls):
- The 23 crashing guides all belong to the **wellness/health networks**
  (`network_id` a6486f6d / 9bf1b71d) yet are attached to the **beauty** Miami
  city, so they surface on the beauty site. After the crash fix they render 200
  but show wellness/health content (yoga, IV therapy, dentists) on a beauty site.
- 3 beauty guides (`how-much-does-balayage-cost-miami`,
  `microblading-vs-powder-brows-miami`, `lash-lift-vs-extensions-miami`) contain
  a literal `{{BUSINESSES}}` placeholder in their `body_markdown` that was never
  substituted — visitors see the raw text "{{BUSINESSES}}".
- On the imported (string-date) guides the byline date renders as the raw ISO
  string rather than "Jun 12, 2026" — cosmetic, because `humantime` str()-falls-back.

The real cure for all three is to normalize the imported guide data (store
`published_at` as a datetime, fix the network/city wiring, substitute or remove
the placeholder). Those are data writes + content decisions, deliberately left
for a human.

### Other pre-launch sweep findings (data/config, flagged not fixed)

- **`hollywood-fl` city has no live subdomain.** It is a beauty-network city
  (status live, ~17 businesses, with a non-UUID `_id` literally "hollywood-fl")
  but there is no `hollywood-fl.knowsbeauty.com` in the Traefik host list, so all
  its businesses are unreachable. Looks like a duplicate of the real `hollywood`
  city — merge or give it a subdomain (a decision + data write).
- **Every other page type is solid.** 651/651 business pages (including all 131
  single-line-address records — the #369 fix holds, no regression), 151 category,
  162 cross, 91 neighborhood, all 26 home pages, and all static/owner pages
  return 200; all deliberately-bad URLs return a clean 404 (never a 500).

### Test-isolation gotcha: don't call attach_templates() in a test

`attach_templates(t)` sets a **module-global `_templates`** in `pages.py` as a
side effect. A unit test that did `attach_templates(Jinja2Templates(...))` with a
throwaway templates object replaced the app's fully-configured templates for the
rest of the session, which made a LATER sync-`TestClient` page-render test
(`test_smoke.py::test_business_jsonld_emits_opening_hours...`) blow up with a
Starlette `BaseHTTPMiddleware` TaskGroup error — a confusing failure miles from
the cause, only visible in the full suite (passed in isolation). Fix: assert
against the app's already-built `app.main.templates` object instead of calling
`attach_templates` with a fresh one. Lesson: never call `attach_templates` (or
anything that mutates a module global) from a test without restoring state.

## Tailwind classes only work if they're in the pre-compiled reference.css (2026-06-20, PR #373)

The site ships a SINGLE pre-built stylesheet (`backend/app/static/css/reference.css`,
one minified line) — there is NO live Tailwind/JIT build. So a utility class typed
in a template renders as **nothing** unless that exact class already has a rule baked
into reference.css. A class that's missing fails silently — no error, no fallback.

This bit the free-tier owner dashboard's locked AI-tool upsell overlay: it used
`bg-white/70` and `backdrop-blur-[1px]`, neither of which is in reference.css (the
only `bg-white` opacities shipped are /5 /10 /40 /60 /85 /90 /95; arbitrary-value
blurs like `[1px]` were never generated). The overlay rendered fully transparent, so
the "Featured listing required" upsell text sat on top of the textarea placeholder
behind it and read as a broken jumble — on the exact screen that asks the owner to pay.
Fix: switch to `bg-white/95` + `backdrop-blur-sm` (both present in reference.css, and
the same readable-overlay recipe the public sticky bars already use).

**Rule for any new template styling:** before using an opacity modifier (`/NN`) or an
arbitrary value (`[...]`), grep reference.css for the escaped selector
(`grep 'bg-white\/95' reference.css`, note the `\/` escaping). If it's absent, pick a
value that IS present rather than assuming Tailwind will generate it. Regression guard:
`tests/test_owner_dashboard_ux.py::TestLockedAiUpsellOverlay` renders the free-tier
dashboard and asserts every overlay class has a real rule in reference.css.

## Driving the owner dashboard with TEST data (no real records touched)

The owner dashboard resolves the logged-in owner's salon by
`businesses.find_one({"claimed_email": <session email lowercased>})`, and the session
cookie is just `sign_session(email)` from `app.services.owner_auth` signed with the
server's `OWNER_SESSION_SECRET`. So to drive `/owners/me` as an owner WITHOUT going
through the email magic-code flow: run `sign_session("<test-email>")` inside the prod
backend container, set it as the `kb_owner_session` cookie in Playwright, and point a
clearly-labelled TEST business's `claimed_email` at that same email. Always use a fake
salon (e.g. slug `zzz-...-DELETEME`), never a real one, and delete it afterward.

Caution: a prior demo session left the REAL "Rossano Ferretti Hair Spa" record with a
fake `stripe_subscription_id` (`sub_demo_screenshot_posey`) + `featured.tier=premium`
and `claimed_email: posey-demo@example.com` while `claim_status` stayed `unclaimed`.
That makes a real salon show as a paid Featured listing (top placement) for free. If
two businesses share one `claimed_email`, whichever sorts first wins the dashboard —
a latent way to show an owner the wrong salon. Clean demo flags off real records.

## Salon detail page must tolerate single-line string addresses (2026-06-20, PR #369)

Imported salon records (about 367 in the beauty network, 256 of them live) store
their address as ONE line of text — e.g. `"2001 N Federal Hwy, Suite 208, Pompano
Beach, FL 33062"` — instead of the structured `{street, city, state, postal_code}`
object the `Business.address` model defines. The detail route built its Google
Maps query with `address.get("street")`, which raised
`AttributeError: 'str' object has no attribute 'get'` on a plain string, so every
one of those live salon pages returned HTTP 500. About 1 in 4 live salon pages.

What did NOT break (verified, so don't chase these): the JSON list API
`GET /api/v1/businesses` (returns raw dicts, no `response_model` — a string
serializes fine; the original audit's "500 on the list API" claim did not
reproduce); the search/category/neighborhood/home pages (no Python-level address
access — they render through `business_card.html`, which never touches address);
the Jinja templates (attribute access on a string yields `Undefined`, not an
error); `voice_provisioning.py` (already `isinstance(addr, dict)`-guarded).

Fix: `_normalize_address()` in `app/routes/public/pages.py` normalizes the
address into a dict at render time (dict passthrough; string → full line kept as
`street` so the Address card still shows it, plus best-effort city/state/zip for
the Maps query and JSON-LD). Display-time only — does NOT rewrite stored data
(that migration needs owner sign-off and is separate). Regression test:
`tests/test_string_address_tolerance.py` (red-green verified).

Tenant-model gotcha discovered while verifying: the beauty network has ~27
separate `city_id`s — they are AREAS, not just Miami (`aventura`, `doral`,
`weston`, `pompano-beach`, `delray-beach`, `boca-raton`, …, plus `miami`). Each
resolves from its own subdomain, and `get_business` filters by the host's
`city_id`. So a Pompano-Beach salon 404s on `miami.knowsbeauty.com` — it's served
under its own area. The string-address salons are spread across MANY of these
areas (the `miami` city alone has 50 live ones). When verifying a specific salon
page, match the salon's `city_id` to the host you request.

Verifying gated pages without flipping the preview gate: send the admin key as
the `X-API-Key` header — the preview-gate middleware bypasses on a matching key.
The key in `~/.claude/gitignore/creds` was 1 char SHORT of the deployed value
(a trailing char got lost); read the exact value from the running container with
`docker exec known-around-town-backend-1 printenv ADMIN_API_KEY`. Playwright:
pass it via `extra_http_headers={"X-API-Key": KEY}`.

## Branded photo-fallback coverage + testing full public pages (2026-06-19, PR #364)

When a salon/neighborhood photo fails to load (many are Unsplash stock URLs that
404), the page must show the branded placeholder tile, not a grey/dark gap. Two
techniques, depending on how the photo is painted:

- **`<img>` tags** → add `onerror="this.onerror=null;this.src='/assets/placeholder-salon.svg';this.style.objectFit='contain';"`. Used in `partials/business_card.html`.
- **CSS `background-image` divs** (can't use onerror) → layer the placeholder as a
  SECOND background beneath the photo: `style='background-image: url("PHOTO"), url("/assets/placeholder-salon.svg"); background-size: cover, contain; background-position: center, center; background-repeat: no-repeat, no-repeat;'`. The first layer (photo) paints on top; the placeholder shows through only on a 404. **Remove the `bg-cover` utility class** when you do this — it forces BOTH layers to cover and crops the brand mark; sizing is set per-layer in the inline style instead.

Coverage map (which public templates have the CSS-background fallback):
- `business.html` hero + thumbnails (#356), `business_card.html` (#356)
- `home.html` (hero, neighborhood grid, Editor's Pick cards, spotlight bg + thumbs, mini-list thumbs), `editorial_guide.html` hero, `neighborhood.html` hero (#364)
- **Keep the existing `{% if photo %}` guards** — only layer beneath a PRESENT photo; never add an empty placeholder box where the design intends a plain dark hero or a themed gradient (e.g. the `home.html` nav-neighborhood `{% else %}` gradient).
- `network_landing.html` city hero (#366): this page's no-photo case shows the brand GRADIENT (not the placeholder SVG), so a broken hero photo degrades to that same gradient — the gradient moved onto the `<img>`'s container div and the `<img>` got `onerror="this.onerror=null;this.style.display='none';"` to hide itself and reveal it. (Pick the fallback that matches each surface's existing no-photo design: SVG for the salon surfaces, gradient here.)
- Still uncovered (follow-up): `business.html:581` map-preview has a bare background but degrades to a branded gradient (low priority).

**Testing full public pages that extend `base.html`:** a bare `jinja2.Environment`
can't even compile them — they use app-registered filters (`markdown`) and globals.
Render through the app's real env instead: `from app.main import templates; templates.env.get_template(name).render(**ctx)`. The footer also needs a `now`
datetime in the context. See `_render_page`/`_page_ctx` in `tests/test_image_fallback.py`.
This lets you assert fallback markup on pages the default seed doesn't populate
(guides, neighborhoods) without seeding them.

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

## Support email configuration (2026-06-12)

The support email `hello@knowsbeauty.com` was hardcoded in ~15 places across templates and email service code. The domain has no mail records so every message to it bounced. The pattern used to make it configurable:

1. `Settings.support_email` in `config.py` (env var `SUPPORT_EMAIL`)
2. Jinja2 global set at module load from env var, overwritten in `on_startup` from DB value
3. `get_support_email()` in `site_settings.py` — DB value takes precedence over env var
4. Admin settings page field saves to DB and updates the Jinja2 global in-process immediately

For any future site-wide text that might need to change: use this same DB-over-env-var-over-default pattern from `site_settings.py`.
