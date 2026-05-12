"""Lookup helpers for content collections, scoped to a (network, city) tenant."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.database import get_db


async def list_neighborhoods(city_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    cur = db.neighborhoods.find({"city_id": city_id, "status": {"$ne": "archived"}})
    return await cur.sort([("order", 1), ("name", 1)]).to_list(length=200)


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
