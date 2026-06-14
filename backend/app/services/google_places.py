"""Google Places API client for fetching business ratings and hours.

WHY this module exists: Showing a salon's Google star rating and review count is
the single highest-value trust signal we can add to the directory. Consumers
trust Google ratings; displaying them on Miami Knows Beauty pages reduces bounce
and increases claim intent. The AggregateRating JSON-LD emitted from these values
also enables Google to show star snippets in search results, which increases
click-through rate by 15–30% for queries where the snippets appear (approximate
industry estimate; varies by query type and market).

Opening hours are also fetched alongside ratings: they enable the
openingHoursSpecification JSON-LD block (which powers "Open · Closes 6pm"
in Google's Knowledge Panel) and the hours display in the business listing itself.

Ratings and hours are cached in the business document so page loads never block
on a live API call. The admin sync endpoint refreshes them on demand.

WHY Places API (New): The project uses Google's Places API (New)
(places.googleapis.com), not the legacy Maps Platform Places API
(maps.googleapis.com/maps/api/place/…). The two APIs require separate
enablement in Google Cloud Console; keys created with only the new API active
receive REQUEST_DENIED on legacy endpoints. The new API also provides
regularOpeningHours with integer hour/minute fields instead of the legacy
"0900" time string, so the hours parser differs accordingly.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Optional

import httpx

from app.config import get_settings
from app.models import HoursEntry

log = logging.getLogger(__name__)

# WHY: Places API (New) endpoints — not the legacy Maps Platform places endpoints.
# Text Search: POST with JSON body; auth via X-Goog-Api-Key header.
# Place Details: GET /v1/places/{place_id}; same header auth.
_PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_PLACES_DETAILS_BASE = "https://places.googleapis.com/v1/places"

# WHY: 8 seconds allows for transient network latency without blocking the
# sync endpoint so long that the admin's browser times out. Google's API
# typically responds in 200–800ms on a healthy connection.
_TIMEOUT_SECONDS = 8

# WHY: minimum name-similarity ratio (0–1) required before we trust a Text
# Search result. Google's top result is usually correct, but with a short or
# common name ("Nails", "Salon") a completely unrelated business can rank
# first. A threshold of 0.4 allows abbreviations, punctuation differences, and
# common words ("Beauty", "Studio") while rejecting clearly wrong matches.
# Lowered from the conventional 0.6 because salon names often legitimately
# omit city or business-type words that the Google listing includes.
_NAME_SIMILARITY_THRESHOLD = 0.40

# WHY: Google Places day-of-week integer (0=Sunday … 6=Saturday) maps to
# HoursEntry.day strings. This lets us translate the API's numeric format
# into the model's named-day format without a conditional chain.
_DAY_INT_TO_STR = {0: "sun", 1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat"}

# WHY: retry up to 3 times on 429 rate-limit responses. Google's quotas reset
# per second, so sleeping a few seconds between attempts recovers most bursts.
# 3 retries keeps total per-business wait under 15s (2 + 4 + 8) in the worst case.
_MAX_RETRY_ATTEMPTS = 3

# WHY: 2s base delay; doubles each attempt (2s → 4s → 8s). Exponential backoff
# is the standard approach for rate-limited APIs — it spaces out retries so
# quota has time to replenish rather than hammering the same second again.
_RETRY_BACKOFF_SECONDS = 2.0


@dataclass
class PlaceRating:
    place_id: str
    rating: float                    # 1.0 – 5.0
    review_count: int
    hours: List[HoursEntry] = field(default_factory=list)  # empty = not available


def is_configured() -> bool:
    """True when GOOGLE_PLACES_API_KEY is set."""
    return bool(get_settings().google_places_api_key)


async def lookup_rating(
    business_name: str,
    city: str,
    state: str = "FL",
    existing_place_id: Optional[str] = None,
) -> Optional[PlaceRating]:
    """Return the Google rating (and hours) for a business, or None on any failure.

    When ``existing_place_id`` is provided, uses the faster Place Details
    endpoint instead of a name-based text search.

    WHY None on failure rather than raising: the caller (admin sync) handles
    an entire batch; a single failed lookup should not abort the rest.
    """
    api_key = get_settings().google_places_api_key
    if not api_key:
        log.debug("GOOGLE_PLACES_API_KEY not configured — skipping rating lookup")
        return None

    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        if existing_place_id:
            return await _fetch_by_place_id(client, existing_place_id, api_key)
        return await _search_and_fetch(client, business_name, city, state, api_key)


def _name_similarity(a: str, b: str) -> float:
    """Case-insensitive token-overlap ratio between two business names.

    WHY SequenceMatcher on lowercased strings: gives partial credit for
    matching word stems even when word order or small details differ.
    """
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _parse_hours(opening_hours: dict) -> List[HoursEntry]:
    """Convert a Places API (New) regularOpeningHours object to a HoursEntry list.

    Returns an empty list when hours are unknown so callers can distinguish
    "unknown" (empty list → skip update) from "closed this day" (entry with
    closed=True → store explicitly).

    WHY periods not weekdayDescriptions: periods gives machine-readable open/close
    times we can store and re-render in any format; weekdayDescriptions is
    display-only and may be localised.

    WHY return [] when day_map is empty after parsing: an empty periods list
    means Google has no hour data. Returning [] preserves any manually-entered
    hours rather than incorrectly overwriting them with "always closed".

    WHY integer hour/minute fields: Places API (New) uses {day, hour, minute}
    integers (e.g. {"day": 1, "hour": 9, "minute": 0}) rather than the legacy
    "time": "0900" string format.
    """
    if not opening_hours:
        return []

    periods = opening_hours.get("periods") or []
    day_map: dict[int, tuple[str, str]] = {}
    for period in periods:
        open_info = period.get("open") or {}
        close_info = period.get("close") or {}
        day_int = open_info.get("day")
        open_hour = open_info.get("hour")
        open_min = open_info.get("minute", 0)
        close_hour = close_info.get("hour")
        close_min = close_info.get("minute", 0)
        if day_int is None or open_hour is None or close_hour is None:
            continue
        opens_fmt = f"{open_hour:02d}:{open_min:02d}"
        closes_fmt = f"{close_hour:02d}:{close_min:02d}"
        day_map[day_int] = (opens_fmt, closes_fmt)

    # WHY: no valid open periods → hours unknown, not "all closed"
    if not day_map:
        return []

    result: List[HoursEntry] = []
    for day_int in range(7):
        day_str = _DAY_INT_TO_STR[day_int]
        if day_int in day_map:
            opens_fmt, closes_fmt = day_map[day_int]
            result.append(HoursEntry(day=day_str, opens_at=opens_fmt, closes_at=closes_fmt))
        else:
            result.append(HoursEntry(day=day_str, closed=True))
    return result


async def _search_and_fetch(
    client: httpx.AsyncClient,
    business_name: str,
    city: str,
    state: str,
    api_key: str,
) -> Optional[PlaceRating]:
    """Look up a business by name + city, then fetch its rating and hours.

    WHY no type restriction: a type=beauty_salon filter would silently exclude
    nail salons, barbershops, spas, waxing studios, and other business types
    that legitimately appear in a beauty directory. Leaving the type open and
    relying on name + city matching gives accurate results for the full range
    of beauty businesses.

    WHY delegate to _fetch_by_place_id after text search: rating + hours
    come back in a single Details call with the full field set. On first
    discovery we do two calls (search + details); on subsequent syncs we skip
    the text search entirely because place_id is already cached.

    WHY POST with JSON body: Places API (New) Text Search uses POST, not GET,
    with the query in the JSON body and auth in the X-Goog-Api-Key header.
    """
    query = f"{business_name} {city} {state}"
    headers = {
        "X-Goog-Api-Key": api_key,
        # WHY: field mask requests only the fields we need (id and
        # display name for the match check). Rating + hours come from
        # the subsequent Details call so are not requested here.
        "X-Goog-FieldMask": "places.id,places.displayName",
    }
    data: Optional[dict] = None
    for attempt in range(_MAX_RETRY_ATTEMPTS + 1):
        try:
            r = await client.post(
                _PLACES_SEARCH_URL,
                json={"textQuery": query},
                headers=headers,
            )
        except Exception as exc:
            log.warning("Places text search failed for %r: %s", query, exc)
            return None
        if r.status_code == 429:
            if attempt < _MAX_RETRY_ATTEMPTS:
                delay = _RETRY_BACKOFF_SECONDS * (2 ** attempt)
                log.info(
                    "Rate-limited searching %r; retrying in %.1fs (attempt %d/%d)",
                    query, delay, attempt + 1, _MAX_RETRY_ATTEMPTS,
                )
                await asyncio.sleep(delay)
                continue
            log.warning(
                "Rate-limited searching %r after %d retries — giving up",
                query, _MAX_RETRY_ATTEMPTS,
            )
            return None
        try:
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            log.warning("Places text search failed for %r: %s", query, exc)
            return None
        break

    if data is None:
        return None

    places = data.get("places") or []
    if not places:
        log.info("No Places match for %r", query)
        return None

    # WHY: take the first result (highest-relevance match), but guard against
    # a completely wrong business ranking first for a short or common name.
    top = places[0]
    top_name = (top.get("displayName") or {}).get("text", "")
    similarity = _name_similarity(business_name, top_name)
    if similarity < _NAME_SIMILARITY_THRESHOLD:
        log.info(
            "Top Places result %r for query %r has low name similarity %.2f — skipping",
            top_name, query, similarity,
        )
        return None

    place_id = top.get("id")
    if not place_id:
        # WHY: a result without an id can't be stored usefully — without it we
        # can't refresh on future syncs via the cheaper Details endpoint.
        log.warning("Places result for %r missing id — skipping", query)
        return None

    # Fetch full details (rating + hours) now that we have the place id.
    return await _fetch_by_place_id(client, place_id, api_key)


async def _fetch_by_place_id(
    client: httpx.AsyncClient,
    place_id: str,
    api_key: str,
) -> Optional[PlaceRating]:
    """Refresh rating and hours for a known place_id (faster, no name-match uncertainty).

    WHY GET /v1/places/{id}: Places API (New) Place Details uses a resource
    path rather than a query parameter. The field mask header controls which
    fields are returned (and billed for).
    """
    headers = {
        "X-Goog-Api-Key": api_key,
        # WHY: request rating, review count, and opening hours together
        # in one call. Listing hours separately would double billing.
        "X-Goog-FieldMask": "id,rating,userRatingCount,regularOpeningHours",
    }
    data: Optional[dict] = None
    for attempt in range(_MAX_RETRY_ATTEMPTS + 1):
        try:
            r = await client.get(
                f"{_PLACES_DETAILS_BASE}/{place_id}",
                headers=headers,
            )
        except Exception as exc:
            log.warning("Places details fetch failed for place_id=%r: %s", place_id, exc)
            return None
        if r.status_code == 429:
            if attempt < _MAX_RETRY_ATTEMPTS:
                delay = _RETRY_BACKOFF_SECONDS * (2 ** attempt)
                log.info(
                    "Rate-limited fetching place_id=%r; retrying in %.1fs (attempt %d/%d)",
                    place_id, delay, attempt + 1, _MAX_RETRY_ATTEMPTS,
                )
                await asyncio.sleep(delay)
                continue
            log.warning(
                "Rate-limited for place_id=%r after %d retries — giving up",
                place_id, _MAX_RETRY_ATTEMPTS,
            )
            return None
        try:
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            log.warning("Places details fetch failed for place_id=%r: %s", place_id, exc)
            return None
        break

    if data is None:
        return None

    rating_val = data.get("rating")
    if rating_val is None:
        return None
    return PlaceRating(
        place_id=place_id,
        rating=float(rating_val),
        review_count=int(data.get("userRatingCount", 0)),
        hours=_parse_hours(data.get("regularOpeningHours")),
    )
