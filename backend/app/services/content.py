"""Lookup helpers for content collections, scoped to a (network, city) tenant."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.database import get_db


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
    return await get_db().businesses.find_one({"city_id": city_id, "slug": slug})


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


# WHY: the fields every search term is matched against. Beyond free-text name
# and description, we include the slug arrays so a term like "nails" or
# "brickell" finds a salon by its category or neighborhood even though those
# words never appear in the salon's own copy. The slugs ARE the searchable
# words for Miami's single-word categories/neighborhoods ("nails", "hair",
# "brickell", "wynwood"); a regex (substring) match also catches multi-word
# slugs like "brickell-ave-mary-brickell-village" from a "brickell" term.
_SEARCH_FIELDS = (
    "name",
    "short_description",
    "tags",
    "category_slugs",
    "neighborhood_slugs",
)


async def search_businesses(
    city_id: str, query: str, *, limit: int = 40
) -> List[Dict[str, Any]]:
    """Full-text-style search across a business's name, description, tags,
    category, and neighborhood.

    Uses case-insensitive regex because Atlas free-tier clusters do not
    guarantee a $text index is available. Regex on name + short_description +
    tags + category/neighborhood slugs covers the vast majority of real search
    intent ("lash bar", "curly hair", "nail art", "nails brickell").

    Multi-word queries use AND-across-terms semantics: every whitespace-
    separated term must match at least one searchable field. So "nails
    brickell" returns nail salons in Brickell — it does NOT require any single
    field to contain the literal phrase "nails brickell" (no business has it).
    """
    # WHY: split into terms so a multi-word query like "nails brickell" matches
    # nail salons that are in Brickell, instead of looking for the literal
    # contiguous phrase "nails brickell" (which no business name or slug holds).
    terms = query.split()
    if not terms:
        return []

    # WHY: re.escape prevents a term like "a.b" from being treated as a regex
    # wildcard and matching "a<any-char>b" — user input must be literal.
    # Each term gets its own $or across all searchable fields; combining the
    # per-term blocks with $and requires EVERY term to match SOMEWHERE.
    and_clauses: List[Dict[str, Any]] = []
    for term in terms:
        pattern = re.escape(term)
        and_clauses.append(
            {
                "$or": [
                    {field: {"$regex": pattern, "$options": "i"}}
                    for field in _SEARCH_FIELDS
                ]
            }
        )

    q: Dict[str, Any] = {
        "city_id": city_id,
        "status": "live",
        "$and": and_clauses,
    }
    db = get_db()
    cur = db.businesses.find(q)
    # WHY: featured + editor's pick first — so the best listings surface when
    # the query matches multiple businesses (e.g. "balayage" could match 8).
    cur = cur.sort(
        [("featured.enabled", -1), ("editors_pick", -1), ("quality_score", -1), ("name", 1)]
    )
    cur = cur.limit(limit)
    return await cur.to_list(length=limit)


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
