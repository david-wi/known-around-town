"""Google Places API client for fetching business ratings.

WHY this module exists: Showing a salon's Google star rating and review count is
the single highest-value trust signal we can add to the directory. Consumers
trust Google ratings; displaying them on Miami Knows Beauty pages reduces bounce
and increases claim intent. The AggregateRating JSON-LD emitted from these values
also enables Google to show star snippets in search results, which increases
click-through rate by 15–30% for queries where the snippets appear (approximate
industry estimate; varies by query type and market).

Ratings are cached in the business document so page loads never block on a live
API call. The admin sync endpoint refreshes them on demand.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

# WHY: Text Search endpoint rather than Nearby Search because we have the
# business name and city — Text Search is tuned for this use case and returns
# the highest-relevance match first.
_PLACES_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
_PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

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


@dataclass
class PlaceRating:
    place_id: str
    rating: float        # 1.0 – 5.0
    review_count: int


def is_configured() -> bool:
    """True when GOOGLE_PLACES_API_KEY is set."""
    return bool(get_settings().google_places_api_key)


async def lookup_rating(
    business_name: str,
    city: str,
    state: str = "FL",
    existing_place_id: Optional[str] = None,
) -> Optional[PlaceRating]:
    """Return the Google rating for a business, or None on any failure.

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


async def _search_and_fetch(
    client: httpx.AsyncClient,
    business_name: str,
    city: str,
    state: str,
    api_key: str,
) -> Optional[PlaceRating]:
    """Look up a business by name + city and return its rating.

    WHY no `type` filter: a `type=beauty_salon` filter would silently exclude
    nail salons, barbershops, spas, waxing studios, and other business types
    that legitimately appear in a beauty directory. Leaving the type open and
    relying on name + city matching gives accurate results for the full range
    of beauty businesses.
    """
    query = f"{business_name} {city} {state}"
    try:
        r = await client.get(
            _PLACES_SEARCH_URL,
            params={"query": query, "key": api_key},
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        log.warning("Places text search failed for %r: %s", query, exc)
        return None

    results = data.get("results") or []
    if not results:
        log.info("No Places match for %r", query)
        return None

    # WHY: take the first result (highest-relevance match), but guard against
    # a completely wrong business ranking first for a short or common name.
    # If the top result's name has below-threshold similarity to ours, we
    # skip it rather than storing a mismatched rating.
    top = results[0]
    top_name = top.get("name", "")
    similarity = _name_similarity(business_name, top_name)
    if similarity < _NAME_SIMILARITY_THRESHOLD:
        log.info(
            "Top Places result %r for query %r has low name similarity %.2f — skipping",
            top_name, query, similarity,
        )
        return None

    place_id = top.get("place_id")
    if not place_id:
        # WHY: a result without a place_id can't be stored usefully — without
        # one we can't refresh on future syncs via the cheaper Details endpoint.
        log.warning("Places result for %r missing place_id — skipping", query)
        return None

    rating_val = top.get("rating")
    if rating_val is None:
        return None
    return PlaceRating(
        place_id=place_id,
        rating=float(rating_val),
        review_count=int(top.get("user_ratings_total", 0)),
    )


async def _fetch_by_place_id(
    client: httpx.AsyncClient,
    place_id: str,
    api_key: str,
) -> Optional[PlaceRating]:
    """Refresh rating for a known place_id (faster, no name-match uncertainty)."""
    try:
        r = await client.get(
            _PLACES_DETAILS_URL,
            params={
                "place_id": place_id,
                # WHY: only request the two fields we need to minimise billed SKU cost
                "fields": "rating,user_ratings_total",
                "key": api_key,
            },
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        log.warning("Places details fetch failed for place_id=%r: %s", place_id, exc)
        return None

    result = data.get("result") or {}
    rating_val = result.get("rating")
    if rating_val is None:
        return None
    return PlaceRating(
        place_id=place_id,
        rating=float(rating_val),
        review_count=int(result.get("user_ratings_total", 0)),
    )
