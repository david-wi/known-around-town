"""Lookup helpers for content collections, scoped to a (network, city) tenant."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.database import get_db
from app.services.ai_caption import CaptionGenerationError, call_gateway_text

log = logging.getLogger(__name__)


async def list_neighborhoods(city_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    # WHY: only surface neighborhoods that actually have businesses — a
    # listed_count of 0 (or missing) means the page would be empty, which
    # hurts SEO and confuses visitors. The field is incremented whenever a
    # business is published to this neighborhood.
    cur = db.neighborhoods.find(
        {"city_id": city_id, "status": {"$ne": "archived"}, "listed_count": {"$gt": 0}}
    )
    return await cur.sort([("order", 1), ("name", 1)]).to_list(length=200)


async def list_cities(network_id: str) -> List[Dict[str, Any]]:
    """Cities that have been seeded under a network, sorted by name.

    Used by the network-wide landing page (rendered at the bare apex host like
    `knowsbeauty.ai.devintensive.com/`) to show visitors which cities they can
    open.
    """
    db = get_db()
    cur = db.cities.find({"network_id": network_id, "status": {"$ne": "archived"}})
    # WHY: alphabetical is the safest default when there's more than one
    # city; it's a stable order that needs no per-city configuration.
    return await cur.sort([("name", 1)]).to_list(length=200)


async def list_categories(
    city_id: str, parent_slug: Optional[str] = None
) -> List[Dict[str, Any]]:
    db = get_db()
    q: Dict[str, Any] = {"city_id": city_id, "status": {"$ne": "archived"}}
    if parent_slug is None:
        q["parent_slug"] = None
    else:
        q["parent_slug"] = parent_slug
    cur = db.categories.find(q)
    return await cur.sort([("order", 1), ("name", 1)]).to_list(length=500)


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
- Use category, neighborhood, tags, and descriptions.
- Include only IDs from the provided candidate list.
- Do not invent IDs.
- Exclude weak or generic matches.
- Return {"business_ids": []} if nothing clearly matches.
"""


async def search_businesses(
    city_id: str, query: str, *, limit: int = 40
) -> List[Dict[str, Any]]:
    """Full-text-style search across a business's name, description, tags,
    category, and neighborhood.

    Uses AI because visitor searches are semantic: "date-night manicure near
    Brickell" should match nail salons in Brickell even when the exact phrase is
    absent from the listing. Mongo still handles only the deterministic tenant
    and status filter.
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
