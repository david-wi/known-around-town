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
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

from app.config import get_settings
from app.models import HoursEntry
from app.services.ai_caption import CaptionGenerationError, call_gateway_text

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

# WHY an LLM judges the match instead of a string heuristic: deciding whether a
# Google listing is the SAME real-world business as one of our directory entries
# is a judgment call, not a string-distance problem. The previous approach scored
# the two names with token/word overlap and accepted them above a threshold. Word
# overlap rewards shared generic words ("spa", "salon") and shared neighborhood
# words ("Brickell") and is blind to meaning, so it made real mistakes — e.g. it
# treated "Kure Spa" and "Lux MedSpa" as the same business because both contained
# "spa" and "Brickell", even though the actual brand ("Kure" vs "Lux") is totally
# different. When one real Google business gets attached to several of our
# listings, all of those listings end up showing the wrong star rating.
#
# The fix: hand the model the two businesses' identifying details (our name + the
# city we searched, and the candidate's display name, full address, and Google
# business type) and ask it directly whether they are the same real-world place.
# We accept the candidate's rating only when the model says yes; on ANY failure
# (model unavailable, timeout, or an answer we can't read) we treat it as NO
# match and leave the business unrated — a wrong rating is worse than no rating.

# WHY use_case "light": this is the same registered, centralized AI gateway
# configuration the public search already uses. It points at a lightweight model
# that is more than capable of a one-line same-business yes/no, and keeps the
# model choice in Admin AI Config (changeable without a redeploy of this app).
_MATCH_USE_CASE = "light"

# WHY 256 tokens: the model only needs to return a tiny JSON object
# ({"same_business": true, "confidence": "high"} is ~15 tokens). Some gateway
# models "think" before answering, and a starved budget would truncate the JSON
# and force a fail-safe NO on every call. 256 is generous headroom for any short
# reasoning plus the answer, while still keeping the response — and its cost —
# small.
_MATCH_MAX_TOKENS = 256

# WHY this system prompt: it pins the model to a single, strict job — decide
# whether two businesses are the same real-world place — and to a machine-
# readable answer so the code can parse it deterministically. The "different
# brand → not the same business even if the type/area match" instruction is the
# exact judgment the old heuristic got wrong (Kure vs Lux).
_MATCH_SYSTEM_PROMPT = (
    "You decide whether two business descriptions refer to the SAME real-world "
    "business — the same physical establishment a customer would walk into.\n\n"
    "Return ONLY a JSON object with this exact shape:\n"
    '{"same_business": true, "confidence": "high"}\n'
    "where same_business is true or false and confidence is \"high\" or \"low\".\n\n"
    "Judge by the BRAND/NAME identity, not by shared generic words. Two "
    "businesses that merely share a category word (spa, salon, nails) or a "
    "neighborhood/city name are NOT the same business if their actual brand "
    "names differ (for example \"Kure Spa\" and \"Lux MedSpa\" are different "
    "businesses even though both are spas in Brickell). Allow for harmless "
    "variations of the SAME brand: extra category words, a location suffix, "
    "abbreviations, punctuation, or word-order differences (for example \"IGK "
    "Salon\" and \"IGK Hair Salon\" ARE the same business). When the address or "
    "Google business type is provided, use it as supporting evidence, but the "
    "brand/name match is what decides it. If you are not confident they are the "
    "same business, answer false."
)

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


class RateLimitError(Exception):
    """Raised when Google's API returns 429 after all retry attempts are exhausted.

    WHY a distinct exception rather than returning None: the sync loop buckets
    None as "no Google match" (permanent — this business has no listing).
    A quota exhaustion is temporary — the daily limit resets overnight and the
    business should be retried. Raising lets the caller count it as a transient
    failure instead of a permanent no-match, so it stays in the unrated queue
    and gets picked up on the next sync run.
    """


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


def _strip_json_code_fence(text: str) -> str:
    """Remove a leading/trailing ``` code fence if the model wrapped its JSON.

    WHY: some gateway models return the JSON inside a Markdown code fence
    (```json ... ```). Stripping it lets json.loads succeed instead of failing
    and forcing a fail-safe NO on an otherwise-valid answer.
    """
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned
    lines = cleaned.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


async def _llm_same_business(
    *,
    searched_name: str,
    city: str,
    state: str,
    candidate_name: str,
    candidate_address: str,
    candidate_types: List[str],
) -> bool:
    """Ask the AI gateway whether a Google candidate is our same real-world business.

    Returns True ONLY when the model explicitly answers that they are the same
    business. Any failure path — gateway unreachable, timeout, non-JSON, an
    answer in an unexpected shape, or anything we cannot confidently read as
    "yes" — returns False. This is a deliberate FAIL-SAFE: attaching the wrong
    Google rating to a listing is worse than leaving that listing unrated, so on
    any uncertainty we decline the match.

    WHY this replaces the old token-overlap heuristic: deciding that "Kure Spa"
    and "Lux MedSpa Brickell" are different businesses (despite sharing the words
    "spa" and "Brickell") is a judgment a model makes correctly and a word-overlap
    score does not.
    """
    our_lines = [f"Our business name: {searched_name}", f"Our city: {city}, {state}"]
    candidate_lines = [f"Candidate name: {candidate_name}"]
    if candidate_address:
        candidate_lines.append(f"Candidate address: {candidate_address}")
    if candidate_types:
        # WHY: Google's business types (e.g. "beauty_salon", "spa") are weak
        # supporting evidence — many distinct businesses share a type — so they
        # inform but never decide the match. The prompt makes that explicit.
        candidate_lines.append(f"Candidate Google business type(s): {', '.join(candidate_types)}")

    user_content = (
        "Business A (our directory listing):\n"
        + "\n".join(our_lines)
        + "\n\nBusiness B (a candidate Google Places result):\n"
        + "\n".join(candidate_lines)
        + "\n\nAre Business A and Business B the same real-world business?"
    )

    try:
        response = await call_gateway_text(
            use_case=_MATCH_USE_CASE,
            system_prompt=_MATCH_SYSTEM_PROMPT,
            user_content=user_content,
            max_tokens_override=_MATCH_MAX_TOKENS,
            cost_tags={
                "product": "known-around-town",
                "feature": "admin.ratings_sync",
                "call": "admin.ratings_sync.match_business",
            },
        )
        parsed = json.loads(_strip_json_code_fence(response))
    except (CaptionGenerationError, json.JSONDecodeError, TypeError, ValueError) as exc:
        # WHY warning + False: a gateway failure or unreadable answer must not
        # accept the candidate. Logged so an operator can see how often the judge
        # is unavailable when auditing a sync run.
        log.warning(
            "AI business-match judge unavailable for %r vs %r — treating as no match: %s",
            searched_name, candidate_name, exc,
        )
        return False

    if not isinstance(parsed, dict):
        log.warning(
            "AI business-match judge returned non-object for %r vs %r — treating as no match",
            searched_name, candidate_name,
        )
        return False

    # WHY: accept ONLY on an explicit boolean True. A missing field, a string,
    # or any other shape is treated as "not confirmed" → no match.
    return parsed.get("same_business") is True


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
    # WHY: list of tuples per day rather than a single tuple — some businesses
    # close for lunch and Google returns two open/close periods on the same day
    # (e.g. 09:00–12:00 and 13:00–18:00). A single-tuple map silently overwrites
    # the morning period with the afternoon one, making the business appear to open
    # in the afternoon. Storing all periods per day preserves the full schedule.
    day_map: dict[int, list[tuple[str, str]]] = {}
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
        if day_int not in day_map:
            day_map[day_int] = []
        day_map[day_int].append((opens_fmt, closes_fmt))

    # WHY: no valid open periods → hours unknown, not "all closed"
    if not day_map:
        return []

    result: List[HoursEntry] = []
    for day_int in range(7):
        day_str = _DAY_INT_TO_STR[day_int]
        if day_int in day_map:
            # WHY: emit one HoursEntry per period — the template iterates the list
            # and renders each row, so two entries for Monday naturally display as
            # "Monday  09:00–12:00" and "Monday  13:00–18:00" without any template
            # changes.  The JSON-LD openingHoursSpecification block does the same.
            for opens_fmt, closes_fmt in day_map[day_int]:
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
        # WHY: request the fields the AI match judge needs — id, display name,
        # full address, and Google business type — so the model has real signal
        # (not just two name strings) when deciding if this is the same business.
        # Rating + hours still come from the subsequent Details call.
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,places.primaryType,places.types"
        ),
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
            raise RateLimitError(f"Rate limit exhausted for query {query!r}")
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

    # WHY: take the first result (highest-relevance match), then have the AI
    # gateway judge whether it is actually the same real-world business before
    # we trust its rating. The model gets our name + city and the candidate's
    # name, address, and Google business type; it rejects look-alikes that merely
    # share a category or neighborhood word (the Kure-vs-Lux failure the old
    # string heuristic let through). On ANY judge failure the call returns False,
    # so an uncertain or unavailable judge leaves the business unrated rather than
    # risking a wrong rating.
    top = places[0]
    top_name = (top.get("displayName") or {}).get("text", "")
    # WHY: a candidate with no name gives the judge nothing to identify it by, so
    # skip the gateway call entirely and treat it as no match. This both avoids a
    # wasted LLM call and keeps us from ever attaching a rating to an unnamed
    # result we couldn't actually verify.
    if not top_name:
        log.info("Top Places result for query %r has no display name — skipping", query)
        return None
    candidate_address = top.get("formattedAddress", "") or ""
    # WHY: primaryType is the single best type; types is the full list. We pass a
    # de-duplicated combined list (primary first) so the model sees every type
    # signal Google has without repeating one.
    candidate_types: List[str] = []
    for t in [top.get("primaryType")] + list(top.get("types") or []):
        if t and t not in candidate_types:
            candidate_types.append(t)

    is_same = await _llm_same_business(
        searched_name=business_name,
        city=city,
        state=state,
        candidate_name=top_name,
        candidate_address=candidate_address,
        candidate_types=candidate_types,
    )
    if not is_same:
        log.info(
            "AI judge: top Places result %r for query %r is not the same business — skipping",
            top_name, query,
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
            raise RateLimitError(f"Rate limit exhausted for place_id {place_id!r}")
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
