"""Lookup helpers for content collections, scoped to a (network, city) tenant."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from app.database import get_db
from app.services.ai_caption import CaptionGenerationError, call_gateway_text

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-process TTL cache for navigation lookups
# ---------------------------------------------------------------------------
# The category / neighborhood / city lists drive the header nav and footer on
# EVERY public page, but they only change on rare admin edits or a re-seed. Yet
# `_base_context` re-queried all three on every single request (3-5 DB
# round-trips per page). PR #452 already batched the editable-copy lookups; this
# is the documented follow-up ("fix #2"): cache the nav lists in-process so they
# aren't re-fetched on every render.
#
# WHY a plain module-level dict of {key: (value, expires_at)} rather than a
# library: it's dependency-free, fast, and exactly enough. We deliberately do
# NOT build cross-process invalidation — production runs multiple uvicorn
# workers, so each worker keeps its own copy and a short TTL bounds how long any
# one worker can serve stale nav data. The admin write routes also call
# `clear_nav_cache()` best-effort, which only clears the worker that handled the
# write; the other workers still self-heal within the TTL. That tradeoff is
# acceptable because nav data changes rarely and a brief (<=TTL) lag before an
# admin edit appears on every worker is harmless for navigation links.

# WHY 120s: nav data changes only on infrequent admin edits / re-seeds, so a
# short TTL is plenty to slash per-request DB load. 120s caps worst-case
# staleness on workers that didn't handle the write to two minutes — short
# enough that an admin sees their change propagate quickly without any
# cross-process invalidation machinery, long enough to absorb the request
# bursts this cache exists to flatten. Chosen by judgment, not measurement;
# safe to tune.
_NAV_CACHE_TTL_SECONDS = 120.0

# Maps a cache key to (cached_value, expires_at_monotonic_seconds).
_nav_cache: Dict[Tuple[Any, ...], Tuple[List[Dict[str, Any]], float]] = {}


def _nav_clock() -> float:
    # WHY: monotonic, not wall-clock — TTL math must be immune to system clock
    # adjustments (NTP steps, DST). Tests monkeypatch this single seam to drive
    # the clock instead of sleeping.
    return time.monotonic()


def _nav_cache_get(key: Tuple[Any, ...]) -> Optional[List[Dict[str, Any]]]:
    entry = _nav_cache.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if _nav_clock() >= expires_at:
        # Expired — drop it so the caller refetches and we don't leak stale keys.
        _nav_cache.pop(key, None)
        return None
    return value


def _nav_cache_set(key: Tuple[Any, ...], value: List[Dict[str, Any]]) -> None:
    _nav_cache[key] = (value, _nav_clock() + _NAV_CACHE_TTL_SECONDS)


def clear_nav_cache() -> None:
    """Drop all cached navigation lists in THIS process.

    Best-effort, single-worker invalidation: admin write routes call this after
    creating/updating/archiving a category, neighborhood, or city so the worker
    that handled the edit reflects it immediately. Other workers (and any future
    process) self-heal within `_NAV_CACHE_TTL_SECONDS`. There is intentionally
    no cross-process broadcast — see the module-level note above.
    """
    _nav_cache.clear()


async def list_neighborhoods(city_id: str) -> List[Dict[str, Any]]:
    cache_key = ("neighborhoods", city_id)
    cached = _nav_cache_get(cache_key)
    if cached is not None:
        return cached
    db = get_db()
    # WHY: only surface neighborhoods that actually have businesses — a
    # listed_count of 0 (or missing) means the page would be empty, which
    # hurts SEO and confuses visitors. The field is incremented whenever a
    # business is published to this neighborhood.
    cur = db.neighborhoods.find(
        {"city_id": city_id, "status": {"$ne": "archived"}, "listed_count": {"$gt": 0}}
    )
    result = await cur.sort([("order", 1), ("name", 1)]).to_list(length=200)
    _nav_cache_set(cache_key, result)
    return result


async def list_cities(network_id: str) -> List[Dict[str, Any]]:
    """Cities that have been seeded under a network, sorted by name.

    Used by the network-wide landing page (rendered at the bare apex host like
    `knowsbeauty.ai.devintensive.com/`) to show visitors which cities they can
    open.
    """
    cache_key = ("cities", network_id)
    cached = _nav_cache_get(cache_key)
    if cached is not None:
        return cached
    db = get_db()
    cur = db.cities.find({"network_id": network_id, "status": {"$ne": "archived"}})
    # WHY: alphabetical is the safest default when there's more than one
    # city; it's a stable order that needs no per-city configuration.
    result = await cur.sort([("name", 1)]).to_list(length=200)
    _nav_cache_set(cache_key, result)
    return result


async def list_categories(
    city_id: str, parent_slug: Optional[str] = None
) -> List[Dict[str, Any]]:
    # WHY: key on BOTH args — `list_categories(city_id)` (top-level nav) and
    # `list_categories(city_id, parent_slug=...)` (a category page's
    # sub-categories) return different result sets and must not share an entry.
    cache_key = ("categories", city_id, parent_slug)
    cached = _nav_cache_get(cache_key)
    if cached is not None:
        return cached
    db = get_db()
    q: Dict[str, Any] = {"city_id": city_id, "status": {"$ne": "archived"}}
    if parent_slug is None:
        q["parent_slug"] = None
    else:
        q["parent_slug"] = parent_slug
    cur = db.categories.find(q)
    result = await cur.sort([("order", 1), ("name", 1)]).to_list(length=500)
    _nav_cache_set(cache_key, result)
    return result


async def get_category(city_id: str, slug: str) -> Optional[Dict[str, Any]]:
    return await get_db().categories.find_one({"city_id": city_id, "slug": slug})


async def get_neighborhood(city_id: str, slug: str) -> Optional[Dict[str, Any]]:
    return await get_db().neighborhoods.find_one({"city_id": city_id, "slug": slug})


async def get_business(city_id: str, slug: str) -> Optional[Dict[str, Any]]:
    return await get_db().businesses.find_one(
        {"city_id": city_id, "slug": slug, "status": "live"}
    )


async def list_businesses(
    city_id: str,
    *,
    category_slug: Optional[str] = None,
    neighborhood_slug: Optional[str] = None,
    featured_only: bool = False,
    limit: int = 60,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"city_id": city_id, "status": "live"}
    if category_slug:
        q["category_slugs"] = category_slug
    if neighborhood_slug:
        q["neighborhood_slugs"] = neighborhood_slug
    if featured_only:
        q["featured.enabled"] = True

    db = get_db()
    cur = db.businesses.find(q)
    cur = cur.sort(
        [
            ("featured.enabled", -1),
            ("editors_pick", -1),
            ("quality_score", -1),
            ("name", 1),
        ]
    )
    cur = cur.skip(offset).limit(limit)
    return await cur.to_list(length=limit)


# WHY: Public search is a semantic selector over business summaries, so sending
# every live listing to the LLM would scale poorly. Current city catalogs are
# far below this size; the cap keeps future prompt cost bounded while preserving
# the same featured/editorial ordering users already see.
SEARCH_AI_CANDIDATE_LIMIT = 80

# WHY: The model only returns business IDs. 450 tokens leaves room for JSON and
# whitespace while preventing the gateway call from turning into copywriting.
SEARCH_AI_MAX_TOKENS = 450

# WHY: "light" is a registered centralized gateway alias. The model choice stays
# in Admin AI Config while code-level cost tags still attribute KAT public search.
SEARCH_AI_USE_CASE = "light"

SEARCH_AI_SYSTEM_PROMPT = """You select local business search results.

Return ONLY JSON with this shape:
{"business_ids": ["business-id"]}

Rules:
- Match the user's meaning, not just exact words.
- Use category, neighborhood, tags, descriptions, what the business is
  known for, and the specific services it offers. A query naming a service
  (e.g. "keratin", "brazilian blowout", "balayage") should match any
  business whose services or known-for text covers that service.
- Include only IDs from the provided candidate list.
- Do not invent IDs.
- Exclude weak or generic matches.
- Return {"business_ids": []} if nothing clearly matches.
"""


async def search_businesses(
    city_id: str, query: str, *, limit: int = 40
) -> List[Dict[str, Any]]:
    """Full-text-style search across a business's name, description, tags,
    category, neighborhood, what it's known for, and the services it offers.

    Uses AI because visitor searches are semantic: "date-night manicure near
    Brickell" should match nail salons in Brickell even when the exact phrase is
    absent from the listing. Including the salon's service-menu names also lets a
    service-intent query ("keratin", "brazilian blowout") match every salon that
    actually offers it, not just one with the word in its description. Mongo still
    handles only the deterministic tenant and status filter.
    """
    search_text = " ".join(query.split())
    if not search_text or limit <= 0:
        return []

    q: Dict[str, Any] = {
        "city_id": city_id,
        "status": "live",
    }
    db = get_db()
    cur = db.businesses.find(q)
    # WHY: featured + editor's pick first — so the best listings surface when
    # the query matches multiple businesses (e.g. "balayage" could match 8).
    cur = cur.sort(
        [("featured.enabled", -1), ("editors_pick", -1), ("quality_score", -1), ("name", 1)]
    )
    cur = cur.limit(SEARCH_AI_CANDIDATE_LIMIT)
    candidates = await cur.to_list(length=SEARCH_AI_CANDIDATE_LIMIT)
    selected_ids = await _select_matching_business_ids(
        query=search_text,
        businesses=candidates,
    )
    selected = set(selected_ids)
    return [business for business in candidates if str(business.get("_id")) in selected][:limit]


async def _select_matching_business_ids(
    *,
    query: str,
    businesses: List[Dict[str, Any]],
) -> List[str]:
    """Select search results with AI rather than regex over listing text.

    WHY: The user's search intent can be broader than listing wording ("mani",
    "self-care day", "natural curls near downtown"). Regex terms either miss
    those matches or over-match incidental words. The LLM receives a bounded
    candidate set that Mongo has already scoped to the city, and callers keep no
    results if the gateway cannot make a reliable semantic decision.
    """
    if not query or not businesses:
        return []

    candidate_ids = {str(business.get("_id")) for business in businesses}
    candidate_payload = [
        {
            "id": str(business.get("_id")),
            "name": business.get("name", ""),
            "short_description": business.get("short_description", ""),
            # WHY: known_for is the "what they're celebrated for" line, often
            # the most service-specific signal a salon has ("known for balayage
            # and keratin"). Including it lets the matcher surface a salon for a
            # service-intent query even when the service isn't in name/tags.
            "known_for": business.get("known_for", "") or "",
            # WHY: a salon's own service-menu item names ("Keratin Treatment",
            # "Brazilian Blowout") are ground-truth for what it offers. Without
            # them, a high-intent query like "keratin" matched only the 1 salon
            # with the word in its description; with them it matches every salon
            # that actually lists the service. Capped at 15 names to keep the
            # candidate payload bounded across up to SEARCH_AI_CANDIDATE_LIMIT
            # candidates (most menus are well under 15; the cap just guards a
            # pathological outlier from bloating the prompt).
            "services": [
                s.get("name", "")
                for s in (business.get("services") or [])[:15]
                if isinstance(s, dict) and s.get("name")
            ],
            "tags": business.get("tags") or [],
            "category_slugs": business.get("category_slugs") or [],
            "neighborhood_slugs": business.get("neighborhood_slugs") or [],
        }
        for business in businesses
    ]

    try:
        response = await call_gateway_text(
            use_case=SEARCH_AI_USE_CASE,
            system_prompt=SEARCH_AI_SYSTEM_PROMPT,
            user_content=(
                f"Search query: {query}\n\n"
                "Candidate businesses:\n"
                f"{json.dumps(candidate_payload, ensure_ascii=True)}"
            ),
            max_tokens_override=SEARCH_AI_MAX_TOKENS,
            cost_tags={
                "product": "known-around-town",
                "feature": "public.search",
                "call": "public.search.match_businesses",
            },
        )
        parsed = json.loads(_strip_json_code_fence(response))
    except (CaptionGenerationError, json.JSONDecodeError, TypeError, ValueError) as exc:
        log.warning("AI business search unavailable; returning no semantic matches: %s", exc)
        return []

    raw_ids = parsed.get("business_ids") if isinstance(parsed, dict) else []
    if not isinstance(raw_ids, list):
        return []

    selected: List[str] = []
    for raw_id in raw_ids:
        business_id = str(raw_id)
        if business_id in candidate_ids and business_id not in selected:
            selected.append(business_id)
    return selected


def _strip_json_code_fence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


async def count_businesses(
    city_id: str,
    *,
    category_slug: Optional[str] = None,
    neighborhood_slug: Optional[str] = None,
) -> int:
    q: Dict[str, Any] = {"city_id": city_id, "status": "live"}
    if category_slug:
        q["category_slugs"] = category_slug
    if neighborhood_slug:
        q["neighborhood_slugs"] = neighborhood_slug
    return await get_db().businesses.count_documents(q)


async def list_editorial_guides(city_id: str, limit: int = 12) -> List[Dict[str, Any]]:
    cur = get_db().editorial_guides.find(
        {"city_id": city_id, "status": "live"}
    ).sort("published_at", -1).limit(limit)
    return await cur.to_list(length=limit)


async def get_editorial_guide(city_id: str, slug: str) -> Optional[Dict[str, Any]]:
    return await get_db().editorial_guides.find_one(
        {"city_id": city_id, "slug": slug}
    )


def active_editorial_headline(city: Dict[str, Any]) -> Optional[str]:
    """Pick the editorial headline that's active right now."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    headlines = city.get("editorial_headlines") or []
    default = None
    for h in headlines:
        if h.get("is_default"):
            default = h.get("headline")
        active_from = h.get("active_from")
        active_until = h.get("active_until")
        if (active_from is None or active_from <= now) and (
            active_until is None or active_until >= now
        ):
            if not h.get("is_default"):
                return h.get("headline")
    return default or (headlines[0].get("headline") if headlines else None)
