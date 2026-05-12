from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.models import Neighborhood
from app.routes.api.v1._auth import require_admin
from app.routes.api.v1._crud import merge_update, now_utc, to_doc

router = APIRouter(prefix="/neighborhoods", tags=["neighborhoods"])


@router.get("")
async def list_neighborhoods(city_id: str = Query(...)) -> List[Dict[str, Any]]:
    cur = get_db().neighborhoods.find({"city_id": city_id}).sort(
        [("order", 1), ("name", 1)]
    )
    return await cur.to_list(length=500)


@router.post("", dependencies=[Depends(require_admin)])
async def create_neighborhood(body: Neighborhood) -> Dict[str, Any]:
    doc = to_doc(body)
    db = get_db()
    if not await db.cities.find_one({"_id": doc["city_id"]}):
        raise HTTPException(404, "City not found")
    if await db.neighborhoods.find_one(
        {"city_id": doc["city_id"], "slug": doc["slug"]}
    ):
        raise HTTPException(409, "Neighborhood already exists")
    await db.neighborhoods.insert_one(doc)
    return doc


@router.patch("/{neighborhood_id}", dependencies=[Depends(require_admin)])
async def update_neighborhood(neighborhood_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    existing = await db.neighborhoods.find_one({"_id": neighborhood_id})
    if not existing:
        raise HTTPException(404, "Neighborhood not found")
    merged = merge_update(existing, patch)
    await db.neighborhoods.replace_one({"_id": neighborhood_id}, merged)
    return merged


@router.delete("/{neighborhood_id}", dependencies=[Depends(require_admin)])
async def archive_neighborhood(neighborhood_id: str) -> Dict[str, str]:
    res = await get_db().neighborhoods.update_one(
        {"_id": neighborhood_id},
        {"$set": {"status": "archived", "updated_at": now_utc()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Neighborhood not found")
    return {"status": "archived"}
