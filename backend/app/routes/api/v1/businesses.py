from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.models import Business
from app.routes.api.v1._auth import require_admin
from app.routes.api.v1._crud import merge_update, now_utc, to_doc

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("")
async def list_businesses(
    city_id: str = Query(...),
    category_slug: Optional[str] = Query(default=None),
    neighborhood_slug: Optional[str] = Query(default=None),
    featured_only: bool = Query(default=False),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=60, le=200),
    offset: int = Query(default=0, ge=0),
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"city_id": city_id}
    if status:
        q["status"] = status
    if category_slug:
        q["category_slugs"] = category_slug
    if neighborhood_slug:
        q["neighborhood_slugs"] = neighborhood_slug
    if featured_only:
        q["featured.enabled"] = True
    cur = (
        get_db()
        .businesses.find(q)
        .sort(
            [
                ("featured.enabled", -1),
                ("editors_pick", -1),
                ("quality_score", -1),
                ("name", 1),
            ]
        )
        .skip(offset)
        .limit(limit)
    )
    return await cur.to_list(length=limit)


@router.get("/by-slug/{city_id}/{slug}")
async def get_business_by_slug(city_id: str, slug: str) -> Dict[str, Any]:
    doc = await get_db().businesses.find_one({"city_id": city_id, "slug": slug})
    if not doc:
        raise HTTPException(404, "Business not found")
    return doc


@router.get("/{business_id}")
async def get_business(business_id: str) -> Dict[str, Any]:
    doc = await get_db().businesses.find_one({"_id": business_id})
    if not doc:
        raise HTTPException(404, "Business not found")
    return doc


@router.post("", dependencies=[Depends(require_admin)])
async def create_business(body: Business) -> Dict[str, Any]:
    doc = to_doc(body)
    db = get_db()
    if not await db.cities.find_one({"_id": doc["city_id"]}):
        raise HTTPException(404, "City not found")
    if await db.businesses.find_one(
        {"city_id": doc["city_id"], "slug": doc["slug"]}
    ):
        raise HTTPException(409, "Business slug already exists in this city")
    await db.businesses.insert_one(doc)
    return doc


@router.patch("/{business_id}", dependencies=[Depends(require_admin)])
async def update_business(business_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    existing = await db.businesses.find_one({"_id": business_id})
    if not existing:
        raise HTTPException(404, "Business not found")
    merged = merge_update(existing, patch)
    await db.businesses.replace_one({"_id": business_id}, merged)
    return merged


@router.delete("/{business_id}", dependencies=[Depends(require_admin)])
async def archive_business(business_id: str) -> Dict[str, str]:
    res = await get_db().businesses.update_one(
        {"_id": business_id},
        {"$set": {"status": "archived", "updated_at": now_utc()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Business not found")
    return {"status": "archived"}
