# Miami Knows Beauty — Lessons & Gotchas

## Routing

- **Always use the `miami.` subdomain** when testing locally or hitting production URLs. The base domain (`knowsbeauty.ai.devintensive.com`) has no city tenant attached and returns tenant-less responses with no businesses.
- Production: `miami.knowsbeauty.ai.devintensive.com`

## Deployment

- **No GitHub Actions CI** — `gh pr checks` returns 401. Verify deploys by SSH-ing to the server and confirming the container is running the expected git SHA.
- **Auto-deploy webhook** fires on push to `main`. Container is typically live within ~60 seconds.
- Production container check: `ssh ... docker ps` and confirm `STATUS` shows `Up`, not `Restarting`.

## `gh pr merge` Flag Order

- **MUST be**: `gh pr merge N --squash --auto` (PR number first, then flags)
- Reversed order (`gh pr merge --squash --auto N`) returns a 401 GraphQL error — misleading; it's actually a CLI parsing bug where the number gets treated as part of the flag.

## Playwright

- **Use Python Playwright** (`playwright.sync_api`), not Node.js — Node Playwright is not installed on this machine.
- Always pass `Host: miami.knowsbeauty.localhost` or use the full production subdomain URL to get city tenant routing.

## Commit Author

- Always `--author "David <david@expertly.com>"` — the git config defaults to `david@Karissas-Laptop.local` which leaks the machine name.

## Owner Acquisition Funnel

- The `/owners` page is the main entry point for businesses wanting to claim their listing.
- Neighborhood and category listing pages are likely SEO landing points for owners (e.g., "Brickell salons"). As of PR #73 (2026-06-10), both pages have a "For Business Owners" footer banner after the business grid pointing to `/owners`.
- Individual business detail pages also have a claim CTA, but the listing grid pages are the higher-traffic landing zone.

## Founding Partner Badge

- `is_founding_partner: True` is set on a business when a claim is verified (PR #72, 2026-06-10).
- The owners page explicitly promises this badge to early claimers — it is a contractual promise, not a nice-to-have. The smoke test in `test_admin_claims.py::test_verify_claim_still_works` guards against this promise being broken silently.

## Search

- The home page search bar posts to `/search` — as of PR #74 (2026-06-10) this route exists.
- `search_businesses()` in content.py uses `re.escape` + MongoDB regex (case-insensitive) rather than `$text` index — Atlas free-tier doesn't guarantee a text index is set up.
- Search template has three states: results grid, zero-results (with category chip browse links and owner claim CTA), no-query (just browse chips).
- The Google JSON-LD Sitelinks Search Box in `home.html` references `/search?q={search_term_string}` — this is now functional.

## Claim Form — Business Name Matching

- **The claim form uses client-side matching against an embedded `DIRECTORY` array** — no server round-trip. The array contains all businesses in the city's network (name + id + slug).
- **Suggestions use word-overlap scoring** (PR #80, 2026-06-10): +2 for a word boundary match (`\b` prefix), +1 for substring. Top 3 shown as pill buttons.
- The `showError(message, showBrowse)` call determines whether suggestions appear. `showBrowse=true` is passed on name-not-found errors; it triggers both the browse hint and the suggestion pills.
- Business name input ID: `#claim-form__business-name`. Hidden ID field: `#claim-form__business-id`. Suggestions container: `#claim-form__suggestions`.
- The `DIRECTORY` variable and all JS is inside an IIFE on the `/owners` page. All functions are declared with `function` keyword (not `var fn = function(){}`), so hoisting allows forward-references safely.

## Owner Dashboard Pending State

- When an owner submits a claim but is not yet verified, `/owners/me` shows a pending state with the claim's listing name and a "view it now" link.
- As of PR #80 (2026-06-10), this state also shows 3 feature-preview cards (Edit your listing / AI marketing tools / Featured upgrade). These are promise/anticipation cards — they make the wait feel purposeful.
- The upgrade button on the pending state page shows `$29/month` (fixed PR #83, 2026-06-10). The supporting note reads `or $290/year — that's $24/month · first month free`, matching the pricing page exactly.
- **Pricing source of truth is `pricing.html`** — any template that shows a price must match it. The dashboard had drifted to `$99/year` (stale) before the fix.

## Page Title Brand Name — Always `{city} {network}`

- The full brand name is `"{city.name} {network.name}"` → "Miami Knows Beauty". `network.name` alone is just "Knows Beauty" (missing "Miami").
- All `seo_title` fallbacks in routes must use `f"... {city.get('name', '')} {tenant.network.get('name', '')}"` (city first). Using `{network} {city}` order produces "Knows Beauty Miami" which reads as gibberish.
- Business detail pages already had the correct order. Category, neighborhood, and neighborhood-category pages had the wrong order — fixed in PR #82 (2026-06-10).
- Always include `''` empty-string defaults (`city.get('name', '')`) so a missing DB field renders blank rather than the literal word "None" in a page title.

## GitHub Actions CI

- CI runs smoke tests on every push to `main` and every PR. As of PR #85 there are **85 tests** in `test_smoke.py`.
- `gh pr checks --watch` works correctly to wait for CI before confirming merge.
- Post-merge CI run also runs (on the squash commit to main) — both the PR check and the merge check show "pass".
- **Deploy is fast** — container restarts within ~8 seconds of a merge to main (webhook fires almost immediately). The container start time after a fresh deploy is very close to the merge timestamp.

## Business Detail JSON-LD Enrichment (PR #81, 2026-06-10)

- Business detail pages use specific schema subtypes (HairSalon, NailSalon, DaySpa, BeautySalon) — do NOT downgrade to LocalBusiness; the subtypes unlock additional Knowledge Panel fields.
- Four fields added: `image` (hero photo), `@id` (canonical URL), `sameAs` (Instagram + website), plus a BreadcrumbList JSON-LD block.
- **Critical Jinja2 ordering rule**: variables used inside `{% block head_extra %}` must be SET inside that same block, before the point where they're used. Variables defined in `{% block content %}` are NOT available in `head_extra` because content renders after head_extra in Jinja2's block-inheritance order. The original template had `_og_hero_url` defined after the script block that needed it — a silent bug that caused the `image` field to always be empty.
- `namespace(n=2)` is the correct Jinja2 idiom for a mutable counter inside `{% if %}` scopes. Plain `{% set n = n+1 %}` inside an `{% if %}` block doesn't persist back to the outer scope.
- `sameAs` guard: check `'instagram.com' in business.instagram` before prefixing with the full URL — some records store handles (`@salon`) and some store full URLs. Both are valid inputs.
- BreadcrumbList home URL derived with `canonical_url|replace('/b/' ~ business.slug, '')` — works because business page URLs always have the form `/b/<slug>` and slugs are alphanumeric-plus-hyphens with no `/b/` substring.

## Social Share (og:image) Coverage

All public-facing pages now have og:image. Base template also renders twitter:image from the same value.

- Home page: `hero_photo_url` from city record ✓
- Business detail pages: first photo from `business.photos[]` ✓ (PR #81)
- Category pages: first business photo → city hero fallback ✓ (PR #84)
- Neighborhood pages: same pattern ✓ (PR #84)
- Neighborhood+category pages: same pattern ✓ (PR #84)
- Search page: first result's photo → city hero fallback ✓ (PR #85)
- Owners page: city hero photo ✓ (PR #85) — marketing/acquisition page, not a listing page
- Pricing page: city hero photo ✓ (PR #85) — same rationale
- Pattern for listing pages: `next((b["photos"][0]["url"] for b in businesses if b.get("photos")), city.get("hero_photo_url"))`
- Base template renders `og:image` only when `og_image` is truthy — safe to omit from routes that don't have a sensible image (owner dashboard, login, admin pages)

## ItemList JSON-LD (PR #86, 2026-06-10)

- Category pages (`/c/<slug>`), neighborhood pages (`/n/<slug>`), and neighborhood+category pages now include an ItemList JSON-LD block enumerating the businesses shown on the page.
- The block is emitted only when businesses are present (`item_list_jsonld=None` suppresses the script block entirely in the template).
- Business list built via `_build_item_list_jsonld()` helper in `pages.py` — filters out businesses missing `slug` or `name` to avoid invalid entries. Deduplicates logic across all three route handlers.
- Template uses `{{ item_list_jsonld | tojson }}` — the Jinja2 `tojson` filter HTML-escapes and marks output as safe, so no manual escaping needed.
- **Test for neighborhood+category must handle absent block:** if the seed has no businesses at an intersection (e.g. Wynwood+hair could be empty), the route correctly returns `None` and no block is emitted. The smoke test for this page type skips structural assertions in that case.
- As of PR #86 there are **88 tests** in `test_smoke.py`.

## Pending — Blocked on David

- **Stripe keys** needed to activate the payment flow (`stripe_billing.py` is fully built): `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_PRO`
- **GA4 Measurement ID** needed to activate analytics (tracking code already in base template)
- **`www.knowsbeauty.com` DNS** currently returns 410 — needs to point at the correct server
- **Design-partner outreach**: 10 draft DMs/emails ready; need per-message approval before sending
