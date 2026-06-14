
## 2026-06-14 — Seed behavior notes

**KAT_ALLOW_PRODUCTION_RESET does NOT hard-delete unmatched businesses.**
When a seed file is run with this flag, it upserts businesses by slug.
Businesses already in the DB that don't match any slug in the seed file are
left untouched — they are NOT deleted. Only businesses whose slugs ARE in
the seed file get updated/inserted. This means you can safely add 5 businesses
to an existing city's seed file without losing the other businesses.

**`get_db()` is synchronous — never `await` it.**
`get_db()` returns a Motor database object directly, not a coroutine.
Using `await get_db()` raises `TypeError: object AsyncIOMotorDatabase can't
be used in 'await' expression`. Every seed file uses `db = get_db()`.

**Seed output "N total (X new, Y updated)" counts only what the seed
processed**, not the total live count in the DB. A city can show "22 total"
from the seed but have 30 live businesses if the other 8 were inserted
by a previous seed or API call.

## 2026-06-14 — Google Places sync / Fort Lauderdale ratings

**Fort Lauderdale businesses in sub-cities won't match on city-name search.**
Google Places treats Wilton Manors, Las Olas, Flagler Village, and similar
neighborhoods as separate cities. Searching "Business Name Fort Lauderdale FL"
returns no match even when the business exists in Places. The fix: try each
`neighborhood_slug` on the business document (converted to title case) as a
fallback city when the primary search returns nothing. Implemented in
`sync_admin.py` — runs only during discovery (no existing place_id). After the
first successful match, the place_id is cached and future syncs bypass search
entirely, so there's no ongoing performance cost.

**After any Fort Lauderdale sync improvement, trigger a full ratings sync from
/admin/sync** to pick up the new matches. The fallback only helps on the next sync
run — existing no-match records need to be re-synced manually.

**The `lookup_rating` function's `existing_place_id` parameter short-circuits
to the faster place-details endpoint** — it skips the text search entirely.
Always pass this when the place_id is known to avoid wasting Text Search quota.

## 2026-06-14: Edit tool can fail silently during context compaction

If you run an Edit tool call, it reports success, but a subsequent `grep` still shows the old text — this isn't a permission issue. It typically happens when context compaction occurs in between: the edit lands in the previous context window but the next window's tool session state doesn't confirm it. If `grep` shows the old text, run the Edit again fresh. The second attempt (in a fresh context) succeeded immediately.

## 2026-06-14: PR #318 included search title fix

The search page title fix (adding city name) was merged as part of PR #318 "feat(seo): add aggregateRating + openingHours JSON-LD tests; fix search title". Don't create new PRs for this — it's done.

## Seed scripts wipe Google ratings on every deploy (fixed 2026-06-14, PRs #320 and #323)

**Root cause (two-layer bug):** Every code deploy re-runs all 26 city seed scripts. Those scripts do a full database replace on each business, deleting any field they don't explicitly carry forward. Google ratings (`google_rating`, `google_place_id`, etc.) were never in that carry-forward list — so ratings vanished on every deploy.

**Why two PRs were needed:** PR #320 fixed the shared `upsert()` helper in `_helpers.py`. But all 26 city scripts (Miami, Fort Lauderdale, Boca Raton, etc.) have their **own** inline database update logic that bypasses `upsert()` entirely. PR #323 added Google field preservation to all 26 inline blocks.

**Detection:** Check `miami.knowsbeauty.com/admin/sync`. If "Have Google rating" is far below the last sync count, a deploy ran and wiped ratings. Re-trigger at `POST /admin/sync/ratings`. Recovery takes ~3 minutes for 1,002 businesses.

**Pattern to watch for:** Whenever a new city seed script is added, the Google preserve fields must be included in its update loop. The fields to preserve: `google_place_id`, `google_rating`, `google_review_count`, `google_rating_synced_at`.
