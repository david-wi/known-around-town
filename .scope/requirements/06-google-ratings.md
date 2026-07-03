# Google Business Profile Ratings

## Overview

Display Google star ratings and review counts on salon pages and directory cards. Add AggregateRating JSON-LD structured data for Google search result rich snippets. Provide an admin sync endpoint to pull ratings from the Places API on demand.

## Requirements

### KAT-060 — Store Google Places identifiers in the business document

**Status:** implemented

The `Business` model stores `google_place_id`, `google_rating` (float), `google_review_count` (int), and `google_rating_synced_at` (datetime). All four fields default to `None` so existing documents continue to work without a migration.

**Acceptance criteria:**
- `Business` model includes all four fields
- Fields are optional (no migration required)
- Fields survive the seed upsert (carry-forward logic in business upsert preserves them)

---

### KAT-061 — Google Places API client

**Status:** implemented

`backend/app/services/google_places.py` provides `lookup_rating(business_name, city, existing_place_id)` which:
- Uses Text Search when no `place_id` is known (matches by name + city)
- Uses Place Details when a `place_id` is already stored (faster, cheaper)
- Returns `None` on any API failure (never raises — batch callers continue)
- Respects missing API key (gracefully returns `None` when key is absent)

**Acceptance criteria:**
- `is_configured()` returns False when `GOOGLE_PLACES_API_KEY` is unset
- `lookup_rating()` returns a `PlaceRating` dataclass with `place_id`, `rating`, `review_count`
- `lookup_rating()` returns `None` on network error or no-match
- Only requests `rating,user_ratings_total` fields to minimize API cost

---

### KAT-062 — Admin sync page

**Status:** implemented

`GET /admin/sync` shows a coverage dashboard (total salons, how many have ratings, how many need sync) and an API key status indicator.

`POST /admin/sync/ratings` triggers a full sync of all published businesses with asyncio.Semaphore(5) for rate limiting. Redirects back with a result summary (updated / no match / failed counts).

**Acceptance criteria:**
- Page requires admin authentication (same cookie as other admin pages)
- Sync button is disabled and shows "API key required" when key is absent
- Sync runs concurrently (≤5 simultaneous requests) to avoid rate limits
- Page shows result banner after sync completes
- "Sync" link appears in the admin navigation bar

---

### KAT-063 — Rating badge on directory cards

**Status:** implemented

`business_card.html` shows a Google star rating badge (★ 4.7 · 312 reviews) under the business name when `google_rating` is set. Badge is omitted entirely when no rating exists.

**Acceptance criteria:**
- Rating badge appears below the salon name on category/neighborhood/home cards
- Badge is not shown when `google_rating` is null
- Format: `★ 4.7 (312)` (star, decimal rating, review count in parens)
- Badge text meets WCAG AA contrast on the page background.

---

### KAT-064 — Rating on salon detail page

**Status:** implemented

`business.html` shows the Google rating in the hero sidebar card alongside price tier and neighborhood. Format: `4.7 ★ (312)`.

**Acceptance criteria:**
- Rating row appears in the sidebar card on the salon detail page
- Row is not shown when `google_rating` is null
- Rating value and star text meet WCAG AA contrast on the sidebar background.

---

### KAT-065 — AggregateRating JSON-LD structured data

**Status:** implemented

`business.html` emits an `aggregateRating` block inside the existing LocalBusiness JSON-LD when `google_rating` is set. Includes `ratingValue`, `reviewCount`, `bestRating: "5"`, `worstRating: "1"` as required by Google's Rich Results validator.

**Acceptance criteria:**
- `aggregateRating` block is present in JSON-LD when both `google_rating` AND `google_review_count` are set and non-zero
- Block is absent when either value is missing (never emit fabricated counts)
- Passes Google Rich Results Test validator

---

## Configuration

Set `GOOGLE_PLACES_API_KEY` environment variable on the server. Requires:
- Google Cloud project with Places API enabled
- API key with "Places API" permission
- Billing enabled on the Google Cloud project

Cost per sync: ~$0.017 per new business (Text Search), less for refresh (Place Details). Full directory of 55 salons costs approximately $1.

## Notes

- Ratings are cached in the database — no live API call on page load
- Run sync weekly, or after adding new salons
- Ratings do not update automatically
- Google search snippets typically appear within 1–2 weeks of Google's next crawl after the structured data is deployed
