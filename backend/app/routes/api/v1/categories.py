from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.models import Category
from app.routes.api.v1._auth import require_admin
from app.routes.api.v1._crud import merge_update, now_utc, to_doc

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
async def list_categories(
    city_id: str = Query(...),
    parent_slug: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"city_id": city_id}
    if parent_slug is not None:
        q["parent_slug"] = parent_slug
    cur = get_db().categories.find(q).sort([("order", 1), ("name", 1)])
    return await cur.to_list(length=500)


@router.post("", dependencies=[Depends(require_admin)])
async def create_category(body: Category) -> Dict[str, Any]:
    doc = to_doc(body)
    db = get_db()
    if not await db.cities.find_one({"_id": doc["city_id"]}):
        raise HTTPException(404, "City not found")
    if await db.categories.find_one(
        {"city_id": doc["city_id"], "slug": doc["slug"]}
    ):
        raise HTTPException(409, "Category already exists")
    await db.categories.insert_one(doc)
    return doc


@router.patch("/{category_id}", dependencies=[Depends(require_admin)])
async def update_category(category_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    existing = await db.categories.find_one({"_id": category_id})
    if not existing:
        raise HTTPException(404, "Category not found")
    merged = merge_update(existing, patch)
    await db.categories.replace_one({"_id": category_id}, merged)
    return merged


@router.delete("/{category_id}", dependencies=[Depends(require_admin)])
async def archive_category(category_id: str) -> Dict[str, str]:
    res = await get_db().categories.update_one(
        {"_id": category_id},
        {"$set": {"status": "archived", "updated_at": now_utc()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Category not found")
    return {"status": "archived"}
